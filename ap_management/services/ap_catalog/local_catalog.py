import logging
from pathlib import Path
from typing import List

from moma_management.domain.analytical_pattern import AnalyticalPattern

# from sentence_transformers import SentenceTransformer
from .catalog import APCatalog

logger = logging.getLogger(__name__)


class LocalAPCatalog(APCatalog):

    def __init__(self, directory: Path, *, model_name: str = "all-MiniLM-L6-v2"):
        self.catalog: List[AnalyticalPattern] = []
        for path in sorted(directory.glob("*.json")):
            try:
                ap = AnalyticalPattern.model_validate_json(path.read_text())
                self.catalog.append(ap)
            except Exception as e:
                logger.warning("Skipping %s: %s", path.name, e)
        # self._model = SentenceTransformer(model_name)

    async def search(self, task: str) -> List[AnalyticalPattern]:
        """
        Search for Analytical Patterns that match the given task.
        """
        # task_embedding = self._model.encode(task, convert_to_numpy=True)
        return self.catalog

    async def get(self, id: str) -> AnalyticalPattern:
        """
        Retrieve an Analytical Pattern by its ID.
        """
        for ap in self.catalog:
            if str(ap.root.id) == id:
                return ap
        raise ValueError(f"AP with id {id} not found")
