"""Command line of the in-house corpus.

    python -m llm_testbench.eval.corpus.cli build      # select, download, write the manifest
    python -m llm_testbench.eval.corpus.cli download   # fetch what the manifest lists
    python -m llm_testbench.eval.corpus.cli verify     # files against the manifest, summary

``build`` is run once, by whoever defines the corpus; its manifest is versioned. Everyone
else runs ``download``. Both talk to arXiv at one request every three seconds: two hundred
documents take about twenty minutes.
"""

import argparse
import statistics
import sys

from llm_testbench.config import Settings, find_repo_root, get_settings, load_env_file
from llm_testbench.eval.corpus.arxiv import ArxivClient
from llm_testbench.eval.corpus.build import Corpus, build_corpus, corpus_dir, download_corpus
from llm_testbench.eval.corpus.manifest import (
    CORPUS_CONFIG,
    MANIFEST_PATH,
    CorpusConfig,
    Manifest,
)


def _echo(line: str) -> None:
    sys.stderr.write(line + "\n")


def load_corpus(settings: Settings | None = None) -> Corpus:
    """The corpus as the rest of the testbench reads it: the versioned manifest and the
    local cache. Nothing is downloaded here."""
    settings = settings if settings is not None else get_settings()
    manifest = Manifest.load(find_repo_root() / MANIFEST_PATH)
    return Corpus(manifest, corpus_dir(settings.data_dir, manifest.name))


def describe(manifest: Manifest) -> str:
    documents = manifest.documents
    features = [entry.features for entry in documents]
    first = min(entry.submitted for entry in documents).date()
    last = max(entry.submitted for entry in documents).date()
    lines = [
        f"{manifest.name}: {len(documents)} documents, first submitted between {first} and "
        f"{last} (floor {manifest.freshness_floor}), {manifest.candidates_seen} candidates seen",
        "median per document: "
        f"{statistics.median(f.characters for f in features):,.0f} characters, "
        f"{statistics.median(f.tables for f in features):.0f} tables, "
        f"{statistics.median(f.footnotes for f in features):.0f} footnotes, "
        f"{statistics.median(f.formulas for f in features):.0f} displayed formulas",
        "fresh for: " + ", ".join(sorted(manifest.models)),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "download", "verify"))
    args = parser.parse_args(argv)
    load_env_file()
    settings = get_settings()
    root = find_repo_root()
    if args.command == "build":
        config = CorpusConfig.load(settings.resolved_config_dir() / CORPUS_CONFIG)
        manifest = build_corpus(
            config, ArxivClient(), corpus_dir(settings.data_dir, config.name), echo=_echo
        )
        if len(manifest.documents) < config.size:
            _echo(f"only {len(manifest.documents)} of {config.size} documents passed the selection")
        manifest.save(root / MANIFEST_PATH)
        sys.stdout.write(describe(manifest) + "\n")
        return 0
    manifest = Manifest.load(root / MANIFEST_PATH)
    directory = corpus_dir(settings.data_dir, manifest.name)
    if args.command == "download":
        download_corpus(manifest, ArxivClient(), directory, echo=_echo)
    broken = Corpus(manifest, directory).missing()
    sys.stdout.write(describe(manifest) + "\n")
    if broken:
        sys.stdout.write(
            f"{len(broken)} documents missing or altered in {directory}: make corpus-download\n"
        )
        return 1
    sys.stdout.write(f"all files present and matching in {directory}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
