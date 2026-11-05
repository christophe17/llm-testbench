"""arXiv as the source of the in-house corpus: which papers exist, under which license,
first submitted when, and their files.

Three public interfaces, one job each:

- the **OAI-PMH** endpoint lists records by date with their metadata. Its ``arXivRaw``
  format is the only one that carries both the license and the date of every version: the
  date of ``v1`` is when the paper first became public, which is what freshness is about
  (the record's own datestamp moves each time an old paper is revised);
- ``arxiv.org/html/<id>v<n>`` is the paper rendered from its LaTeX source: the reference
  text (``reference.py``). A paper LaTeXML could not render has no such page;
- ``arxiv.org/pdf/<id>v<n>`` is the PDF, the hard-to-parse document itself.

arXiv asks automated clients to stay slow (one request every three seconds) and to say who
they are: :class:`ArxivClient` waits between requests and sends a ``User-Agent``. Nothing
here redistributes a paper: files go to the local cache, and only papers under CC BY 4.0
are selected, so that quoting them in a public golden set is allowed with attribution.
"""

import datetime as dt
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from email.utils import parsedate_to_datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

OAI_URL = "https://oaipmh.arxiv.org/oai"
HTML_URL = "https://arxiv.org/html/{arxiv_id}v{version}"
PDF_URL = "https://arxiv.org/pdf/{arxiv_id}v{version}"
CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"
USER_AGENT = "llm-testbench corpus downloader (public evaluation testbench, one request / 3 s)"

_OAI = "{http://www.openarchives.org/OAI/2.0/}"
_RAW = "{http://arxiv.org/OAI/arXivRaw/}"

Fetch = Callable[[str], bytes | None]
"""URL -> body, or ``None`` when the resource does not exist (404). Injected in tests."""


class ArxivRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    arxiv_id: str
    title: str
    authors: str
    categories: tuple[str, ...]
    """Primary category first."""
    license: str
    submitted: dt.datetime
    """Date of ``v1``: when the paper first became public on arXiv."""
    versions: int

    @property
    def primary_category(self) -> str:
        return self.categories[0] if self.categories else ""


def _text(element: ET.Element | None, name: str) -> str:
    child = element.find(f"{_RAW}{name}") if element is not None else None
    return " ".join((child.text or "").split()) if child is not None else ""


def parse_records(xml: bytes) -> tuple[list[ArxivRecord], str | None]:
    """The records of one OAI-PMH page, and the token of the next page (``None`` on the
    last one). Deleted records and records without a first version are skipped."""
    root = ET.fromstring(xml)
    error = root.find(f"{_OAI}error")
    if error is not None:
        if error.get("code") == "noRecordsMatch":
            return [], None
        raise ValueError(f"OAI-PMH error {error.get('code')}: {error.text}")
    records: list[ArxivRecord] = []
    for record in root.iter(f"{_OAI}record"):
        raw = record.find(f"{_OAI}metadata/{_RAW}arXivRaw")
        if raw is None:
            continue
        versions = raw.findall(f"{_RAW}version")
        first = next((v for v in versions if v.get("version") == "v1"), None)
        date = first.find(f"{_RAW}date") if first is not None else None
        if date is None or not date.text:
            continue
        records.append(
            ArxivRecord(
                arxiv_id=_text(raw, "id"),
                title=_text(raw, "title"),
                authors=_text(raw, "authors"),
                categories=tuple(_text(raw, "categories").split()),
                license=_text(raw, "license"),
                submitted=parsedate_to_datetime(date.text),
                versions=len(versions),
            )
        )
    token = root.find(f"{_OAI}ListRecords/{_OAI}resumptionToken")
    return records, (token.text.strip() if token is not None and token.text else None)


class ArxivClient:
    def __init__(
        self,
        *,
        delay_s: float = 3.0,
        fetch: Fetch | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._delay_s = delay_s
        self._fetch = fetch if fetch is not None else _http_get
        self._sleep = sleep
        self._last_request: float | None = None

    def _get(self, url: str) -> bytes | None:
        if self._last_request is not None:
            wait = self._delay_s - (time.monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        try:
            return self._fetch(url)
        finally:
            self._last_request = time.monotonic()

    def harvest(
        self, *, set_spec: str, since: dt.date, until: dt.date | None = None
    ) -> Iterator[ArxivRecord]:
        """Every record of ``set_spec`` (``cs``, ``physics``…) modified in the window, page
        after page. "Modified" includes old papers revised in the window: the caller
        filters on :attr:`ArxivRecord.submitted`."""
        params = {
            "verb": "ListRecords",
            "metadataPrefix": "arXivRaw",
            "set": set_spec,
            "from": since.isoformat(),
        }
        if until is not None:
            params["until"] = until.isoformat()
        while True:
            body = self._get(f"{OAI_URL}?{urllib.parse.urlencode(params)}")
            if body is None:
                raise ValueError("the OAI-PMH endpoint answered 404")
            records, token = parse_records(body)
            yield from records
            if token is None:
                return
            params = {"verb": "ListRecords", "resumptionToken": token}

    def html(self, arxiv_id: str, version: int = 1) -> str | None:
        """The LaTeXML rendering of the paper, or ``None`` when arXiv has none."""
        body = self._get(HTML_URL.format(arxiv_id=arxiv_id, version=version))
        return body.decode("utf-8", errors="replace") if body is not None else None

    def pdf(self, arxiv_id: str, version: int = 1) -> bytes | None:
        return self._get(PDF_URL.format(arxiv_id=arxiv_id, version=version))


def offline_fetch(directory: Path) -> Fetch:
    """arXiv read from a directory of files instead of the network: what the tests and the
    notebook's live cells use (``tests/fixtures/arxiv``). ``oai_page.xml`` is the first page
    of records, ``oai_page_2.xml`` the one a resumption token leads to; a paper is
    ``<id>v<n>.html`` and ``<id>v<n>.pdf``. A file that is not there is a 404."""

    def fetch(url: str) -> bytes | None:
        if url.startswith(OAI_URL):
            name = "oai_page_2.xml" if "resumptionToken=" in url else "oai_page.xml"
        elif url.startswith(HTML_URL.partition("{")[0]):
            name = url.rpartition("/")[2] + ".html"
        elif url.startswith(PDF_URL.partition("{")[0]):
            name = url.rpartition("/")[2] + ".pdf"
        else:
            return None
        path = directory / name
        return path.read_bytes() if path.is_file() else None

    return fetch


def _http_get(url: str) -> bytes | None:
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body: bytes = response.read()
            return body
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
