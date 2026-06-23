class PlannerError(Exception):
    """Base class for all planner errors."""


class MatchmakerError(PlannerError):
    """LLM or parsing failure inside matchmaker.resolve()."""


class NoApFoundError(PlannerError):
    """Matchmaker succeeded but returned no steps for the task."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ApFetchError(PlannerError):
    """MOMA fetch failed for a specific AP ID."""

    def __init__(self, ap_id: str, cause: Exception):
        self.ap_id = ap_id
        super().__init__(f"Failed to fetch AP '{ap_id}': {cause}")


class PlannerCompositionError(PlannerError):
    """Composer raised an error joining the resolved APs."""
