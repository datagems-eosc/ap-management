from logging import getLogger
from typing import List, Optional, Tuple

from kiota_abstractions.api_error import APIError
from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.generated.moma_management.api.v1.aps.validate.validate_post_request_body import (
    ValidatePostRequestBody,
)
from ap_management.generated.moma_management.moma_management_client import (
    MomaManagementClient,
)

logger = getLogger(__name__)


async def validate_ap(
    moma_svc: Optional[MomaManagementClient], ap: AnalyticalPattern
) -> Tuple[bool, List[str]]:
    """
    Validate the given analytical pattern against the MOMA service.
    Args:
        moma_svc: The MOMA client, or None to skip validation entirely.
        ap: The analytical pattern to be validated.
    Returns:
        A tuple containing a boolean indicating whether the AP is valid or not, and a list of error messages if the AP is invalid.
    """
    if not moma_svc:
        logger.warning("No MOMA service provided, skipping AP validation")
        return True, []

    body = ValidatePostRequestBody()
    body.additional_data = ap.model_dump(by_alias=True, mode="json")
    try:
        await moma_svc.api.v1.aps.validate.post(body=body)
    except APIError as e:
        logger.error(f"Error validating AP: {e}")
        return False, e.additional_data.get("errors", ["Unknown error during AP validation"])

    return True, []
