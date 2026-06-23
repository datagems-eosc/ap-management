import json
import logging
from typing import List

from kiota_abstractions.base_request_configuration import RequestConfiguration
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.generated.moma_management.api.v1.aps.empty_path_segment_request_builder import (
    EmptyPathSegmentRequestBuilder,
)
from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)

from .catalog import APCatalog, APSummary

logger = logging.getLogger(__name__)

_QueryParams = EmptyPathSegmentRequestBuilder.EmptyPathSegmentRequestBuilderGetQueryParameters


class MomaCatalog(APCatalog):
    """MOMA catalog implementation."""

    def __init__(self, moma_svc: MomaManagementClient):
        self.moma_svc = moma_svc

    async def search(self, task: str) -> List[AnalyticalPattern]:
        """
        Search for Analytical Patterns that match the given task.
        """
        params = _QueryParams()
        params.search_q = task

        raw = await self.moma_svc.api.v1.aps.empty_path_segment.get(
            RequestConfiguration(query_parameters=params)
        )

        if not raw:
            return []

        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("items", [])

        results: List[AnalyticalPattern] = []
        for item in items:
            try:
                results.append(AnalyticalPattern.model_validate(item))
            except Exception as e:
                logger.warning("Skipping AP %s: %s", item.get("id", "?"), e)

        return results

    async def get(self, id: str) -> AnalyticalPattern:
        """
        Retrieve an Analytical Pattern by its ID.
        """
        raw = await self.moma_svc.api.v1.aps[id].get()
        if not raw:
            raise ValueError(f"AP with id {id} not found")
        data = json.loads(raw)
        return AnalyticalPattern.model_validate(data)
