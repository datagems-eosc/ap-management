from typing import Any, Dict, List, Protocol, Tuple

from ap_management.services.composer.mapping import Mapping


class CompositionStrategy(Protocol):
    """Base class for composition strategies."""

    def is_possible(self, ap1: Dict[str, Any], ap2: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if the strategy can be applied to the given APs. Returns a tuple of (is_possible, reason). If is_possible is False, reason should explain why."""
        ...

    def generate_mapping(self, ap1: Dict[str, Any], ap2: Dict[str, Any]) -> Tuple[bool, List[Mapping]]:
        """Generate a mapping for the given APs."""
        ...
