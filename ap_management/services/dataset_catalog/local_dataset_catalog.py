import logging
from pathlib import Path
from typing import List

from moma_management.domain.dataset import Dataset

from .catalog import DatasetCatalog

logger = logging.getLogger(__name__)


class LocalDatasetCatalog(DatasetCatalog):
    """Dataset catalog backed by a directory of PG-JSON files. Used for tests and local runs."""

    def __init__(self, directory: Path):
        self.catalog: List[Dataset] = []
        for path in sorted(directory.glob("*.json")):
            try:
                self.catalog.append(Dataset.model_validate_json(path.read_text()))
            except Exception as e:
                logger.warning("Skipping %s: %s", path.name, e)

    async def get(self, id: str) -> Dataset:
        """
        Retrieve a Dataset by its ID.
        """
        for dataset in self.catalog:
            if dataset.root_id == id:
                return dataset
        raise ValueError(f"Dataset with id {id} not found")
