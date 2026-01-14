from logging import getLogger

from fastapi import Response

from ap_management.domain import AnalyticalPattern

logger = getLogger(__name__)


async def display_ap(ap: AnalyticalPattern) -> Response:
    """
    Returns an SVG representation of the Analytical Pattern.
    """
    svg = ap.render_to_svg()
    return Response(content=svg, media_type="image/svg+xml")
