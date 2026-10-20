"""Common interface of the retrieval dataset loaders.

Each public dataset arrives in a different format (Hugging Face Parquet, zips, JSON
on GitHub...); the role of a loader is to absorb this variety and always deliver
the same validated object, :class:`~llm_testbench.eval.types.RetrievalDataset`.
The loaders of the other dataset families (multi-hop QA, text-to-SQL, tables,
images) will arrive with the phases that need them — with their own output types,
but the same contract: declared provenance, validated integrity, explicit sample
mode.
"""

from abc import ABC, abstractmethod

from llm_testbench.eval.types import DatasetInfo, RetrievalDataset


class RetrievalLoader(ABC):
    @property
    @abstractmethod
    def info(self) -> DatasetInfo: ...

    @abstractmethod
    def load(self, split: str = "test", max_queries: int | None = None) -> RetrievalDataset:
        """Load a full split, or one truncated to ``max_queries`` queries.

        A truncated dataset is marked ``sampled=True``: it serves to check the
        mechanics (CI, local iteration), never to produce a number.
        """
