from unittest.mock import AsyncMock, MagicMock

import pytest

from ap_management.services.ap_catalog.moma_catalog import MomaCatalog


@pytest.mark.asyncio
async def test_search_asks_for_every_score():
    """moma-management's default threshold left most real questions with no result."""
    moma = MagicMock()
    moma.api.v1.aps.empty_path_segment.get = AsyncMock(return_value=b'{"aps": []}')

    assert await MomaCatalog(moma).search("Show my performance per topic") == []

    config = moma.api.v1.aps.empty_path_segment.get.call_args.args[0]
    assert config.query_parameters.search_q == "Show my performance per topic"
    assert config.query_parameters.search_threshold == 0
