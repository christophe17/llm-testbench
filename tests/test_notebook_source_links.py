"""The source links in the notebooks must point at the right file and the right line.

The notebooks do not print the code of ``src/``: a markdown cell links to the function or
class — ``[`LLMClient.complete`](../../src/llm_testbench/llm/client.py#L225)`` — and the
reader opens it in the editor, at that line. A line anchor drifts silently: ten lines added
above the method and the link lands on something else, with no error anywhere.

This test collects every such link from the markdown cells of every notebook, imports the
module the path names, resolves the dotted name in it and checks, with ``inspect``, that the
object is defined in that file and starts at that line. The failure message gives the anchor
to write. Offline, no kernel: it reads the notebook JSON.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NOTEBOOKS = sorted(
    path for path in (ROOT / "notebooks").rglob("*.ipynb") if ".ipynb_checkpoints" not in path.parts
)

# [`Dotted.name`](../../src/llm_testbench/pkg/module.py#L123) — relative link, line anchor.
SOURCE_LINK = re.compile(
    r"\[`([A-Za-z_][A-Za-z0-9_.]*)`\]\(((?:\.\./)+src/llm_testbench/[A-Za-z0-9_/]+\.py)#L(\d+)\)"
)


@dataclass(frozen=True)
class SourceLink:
    notebook: Path
    cell: int
    name: str
    target: str
    line: int

    @property
    def label(self) -> str:
        return f"{self.notebook.parent.name}/{self.notebook.stem}:{self.name}"


def collect_links(notebook: Path) -> list[SourceLink]:
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    links: list[SourceLink] = []
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "markdown":
            continue
        for match in SOURCE_LINK.finditer("".join(cell["source"])):
            name, target, line = match.groups()
            links.append(SourceLink(notebook, index, name, target, int(line)))
    return links


LINKS = [link for notebook in NOTEBOOKS for link in collect_links(notebook)]


def test_the_notebooks_link_to_the_source() -> None:
    # Guards the regex itself: a convention change that matched nothing would pass silently.
    assert LINKS, "no source link found in any notebook"


@pytest.mark.parametrize("link", LINKS, ids=lambda link: link.label)
def test_source_link_points_at_the_definition(link: SourceLink) -> None:
    where = f"{link.notebook.relative_to(ROOT)} cell {link.cell}"
    target = (link.notebook.parent / link.target).resolve()
    assert target.is_file(), f"{where}: {link.target} does not exist"

    module_name = ".".join(target.relative_to(SRC).with_suffix("").parts)
    obj: object = importlib.import_module(module_name)
    for part in link.name.split("."):
        if not hasattr(obj, part):
            pytest.fail(f"{where}: `{link.name}` is not defined in {module_name}")
        obj = getattr(obj, part)

    if inspect.isclass(obj) or inspect.isroutine(obj):
        source_file = inspect.getsourcefile(obj)
        _, first_line = inspect.getsourcelines(obj)
    else:
        pytest.fail(f"{where}: `{link.name}` is neither a class nor a function")
    assert source_file is not None, f"{where}: no source file for `{link.name}`"
    defined_in = Path(source_file).resolve()
    expected = f"{link.target}#L{first_line}"
    assert defined_in == target, (
        f"{where}: `{link.name}` is defined in {defined_in.relative_to(ROOT)}, not {link.target}"
    )
    assert link.line == first_line, (
        f"{where}: `{link.name}` starts at line {first_line}, link says {link.line}; "
        f"write `{expected}`"
    )
