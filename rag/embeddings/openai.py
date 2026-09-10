import os
from typing import Any, List, Optional
from rag.bridge.pydantic import Field
from rag.embeddings.base_embeddings import BaseEmbedding
from openai import OpenAI


class OpenAIEmbedding(BaseEmbedding):
    model_name: str = Field(default="text-embedding-3-small")
    api_key: Optional[str] = Field(default=None)
    normalize: bool = True
    embedding_batch_size: int = 8

    def __init__(self, **data: Any):
        super().__init__(**data)

    @property
    def client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key)

    @classmethod
    def class_name(cls) -> str:
        return "OpenAIEmbedding"

    def get_model_dim(self) -> int:
        if "text-embedding-3-small" in self.model_name:
            return 1536
        elif "text-embedding-3-large" in self.model_name:
            return 3072
        elif "text-embedding-ada-002" in self.model_name:
            return 1536
        else:
            raise ValueError(f"⚠️ Modelo OpenAI desconocido: {self.model_name}")

    def _normalize_vector(self, vec: List[float]) -> List[float]:
        import numpy as np
        norm = np.linalg.norm(vec)
        return [v / norm for v in vec] if norm > 0 else vec

    def _call_openai_embedding_api(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        embeddings = [r.embedding for r in response.data]

        if self.normalize:
            embeddings = [self._normalize_vector(e) for e in embeddings]

        return embeddings

    def _embed(self, sentences: List[str]) -> List[List[float]]:
        results = []
        for i in range(0, len(sentences), self.embedding_batch_size):
            batch = sentences[i:i + self.embedding_batch_size]
            results.extend(self._call_openai_embedding_api(batch))
        return results

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed([query])[0]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed([text])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    # ✅ Async usando cliente OpenAI moderno
    async def _aget_query_embedding(self, query: str) -> List[float]:
        response = await self.client.embeddings.acreate(
            model=self.model_name,
            input=[query],
        )
        embedding = response.data[0].embedding
        return self._normalize_vector(embedding) if self.normalize else embedding

    async def _aget_text_embedding(self, text: str) -> List[float]:
        response = await self.client.embeddings.acreate(
            model=self.model_name,
            input=[text],
        )
        embedding = response.data[0].embedding
        return self._normalize_vector(embedding) if self.normalize else embedding
