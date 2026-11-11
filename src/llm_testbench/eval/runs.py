"""What the two kinds of run share: the index a run read, the commit of the code that ran.

A run is the record one arm leaves behind. Each kind has its own module, holding the record,
the function that produces it and its archive: :class:`~llm_testbench.eval.retrieval.RetrievalRun`
in ``eval/retrieval.py``, :class:`~llm_testbench.eval.generation.GenerationRun` in
``eval/generation.py``. Both records say which index they read and what building it cost
(:class:`IndexBuild`), and which commit produced them (:func:`git_state`).
"""

import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class IndexBuild(BaseModel):
    """What it took to have the index this run read (zero when it was already there)."""

    model_config = ConfigDict(frozen=True)

    index_key: str
    documents: int
    chunks: int
    chunks_embedded: int = 0
    embedding_tokens: int = 0
    cost_usd: float | None = 0.0
    seconds: float = Field(ge=0)


def git_state(root: Path | None = None) -> tuple[str | None, bool | None]:
    """(short commit, uncommitted changes?) of the code that ran; (None, None) outside a
    repository (the container image)."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None, None
    return sha or None, bool(status)
