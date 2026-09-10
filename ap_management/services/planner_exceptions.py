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


class DatasetNotFoundError(PlannerError):
    """A requested dataset ID does not exist."""

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        super().__init__(f"Dataset '{dataset_id}' not found")


class DatasetFetchError(PlannerError):
    """MOMA fetch failed for a specific dataset ID."""

    def __init__(self, dataset_id: str, cause: Exception):
        self.dataset_id = dataset_id
        super().__init__(f"Failed to fetch dataset '{dataset_id}': {cause}")


class NoCompatibleDatasetError(PlannerError):
    """
    The planned AP cannot run against any of the requested datasets: one of its operators
    needs a kind of data none of them holds (e.g. a SQL operator over a PDF corpus).
    """

    def __init__(self, requirements: str, dataset_kinds: list[str]):
        self.requirements = requirements
        self.dataset_kinds = dataset_kinds
        super().__init__(
            f"No requested dataset is compatible with the planned AP: {requirements}. "
            f"The given datasets hold: {sorted(set(dataset_kinds)) or 'nothing recognizable'}."
        )


class MagicOperatorError(PlannerError):
    """Building a magic operator AP failed."""
