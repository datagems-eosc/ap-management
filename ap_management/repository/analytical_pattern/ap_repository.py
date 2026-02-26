from typing import List, Optional, Protocol

from ap_management.domain import AnalyticalPattern


class ApRepository(Protocol):
    """
    Facade to store Ap.
    This decorellate AP representation from their physical storage
    """

    async def create(self, ap: AnalyticalPattern,
                     embedding: Optional[List[float]] = None) -> None: ...

    async def get(self, id: str) -> AnalyticalPattern | None: ...

    async def get_by_task_id(self, task_id: str) -> List[str]: ...
    """Retrieve all Analytical Patterns IDS associated to a Task ID"""

    async def enable_embeddings(self, dimensions: int) -> None: ...
    """Create the index for embedding-based search if it does not already exist"""

    async def search(
        self, query_vector: List[float], top_k: int = 10) -> List[tuple[AnalyticalPattern, float]]: ...
    """Search Analytical Patterns by cosine similarity against a pre-computed query vector"""
