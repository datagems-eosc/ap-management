import logging

from moma_management.domain.dataset import Dataset

from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)

from .catalog import DatasetCatalog

logger = logging.getLogger(__name__)


class MomaDatasetCatalog(DatasetCatalog):
    """MOMA-backed dataset catalog."""

    def __init__(self, moma_svc: MomaManagementClient):
        self.moma_svc = moma_svc

    async def get(self, id: str) -> Dataset:
        """
        Retrieve a Dataset by its ID.

        DatasetOutput has the same Kiota nodes/edges shape as the AP endpoint, so this
        mirrors MomaCatalog.get: rebuild a plain PG-JSON dict, then let the domain model
        run its own validation chain on it.
        """
        raw = await self.moma_svc.api.v1.datasets.by_id(id).get()
        if not raw:
            raise ValueError(f"Dataset with id {id} not found")

        data = {
            "nodes": [
                {
                    "id": node.id,
                    "labels": node.labels,
                    "properties": node.properties.additional_data if node.properties else {},
                }
                for node in (raw.nodes or [])
            ],
            "edges": [edge.additional_data for edge in (raw.edges or [])],
        }
        return Dataset.model_validate(data)
