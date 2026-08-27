"""Interface commune des loaders de jeux de retrieval.

Chaque jeu public arrive dans un format différent (Parquet Hugging Face, zips,
JSON sur GitHub...) ; le rôle d'un loader est d'absorber cette variété et de
livrer toujours le même objet validé, :class:`~llm_testbench.eval.types.RetrievalDataset`.
Les loaders des autres familles de jeux (QA multi-hop, text-to-SQL, tableaux,
images) arriveront au fil des phases qui en ont besoin — avec leurs propres types
de sortie, mais le même contrat : provenance déclarée, intégrité validée, mode
échantillon explicite.
"""

from abc import ABC, abstractmethod

from llm_testbench.eval.types import DatasetInfo, RetrievalDataset


class RetrievalLoader(ABC):
    @property
    @abstractmethod
    def info(self) -> DatasetInfo: ...

    @abstractmethod
    def load(self, split: str = "test", max_queries: int | None = None) -> RetrievalDataset:
        """Charge un split complet, ou tronqué à ``max_queries`` requêtes.

        Un jeu tronqué est marqué ``sampled=True`` : il sert à vérifier la
        mécanique (CI, itération locale), jamais à produire un chiffre.
        """
