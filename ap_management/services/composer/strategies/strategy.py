from typing import List, Protocol, Tuple

from moma_management.domain.analytical_pattern import AnalyticalPattern

from ap_management.services.composer.mapping import Mapping


class CompositionStrategy(Protocol):
    """Base class for composition strategies."""

    def is_possible(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> Tuple[bool, str]:
        """Check if the strategy can be applied to the given APs. Returns a tuple of (is_possible, reason). If is_possible is False, reason should explain why."""
        ...

    def generate_mapping(self, ap1: AnalyticalPattern, ap2: AnalyticalPattern) -> Tuple[True, List[Mapping], str]:
        """Generate a mapping for the given APs."""
        ...
