from typing import List, Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    """
    Protocol for embedding text into a fixed-dimensional float vector.
    """

    @property
    def dimensions(self) -> int:
        """Number of dimensions of the produced vectors."""
        ...

    async def embed(self, text: str) -> List[float]:
        """
        Embed a single text string into a float vector.

        Args:
            text: The text to embed.

        Returns:
            A list of floats of length ``self.dimensions``.
        """
        ...
