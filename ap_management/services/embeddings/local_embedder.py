import asyncio
from typing import List

from sentence_transformers import SentenceTransformer


class LocalEmbedder:

    _model: SentenceTransformer
    _dimensions: int

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model = SentenceTransformer(model_name)
        dim = self._model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError(
                f"Could not determine embedding dimensions for model '{model_name}'"
            )
        self._dimensions = dim

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> List[float]:
        vector = await asyncio.to_thread(
            self._model.encode,
            text,
            convert_to_numpy=True,
        )
        return vector.tolist()
