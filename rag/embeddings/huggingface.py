import torch
from typing import TYPE_CHECKING, Any, List, Optional, Union

from rag.bridge.pydantic import Field, PrivateAttr
from rag.constants.default_huggingface import DEFAULT_HUGGINGFACE_EMBEDDING_MODEL
from rag.rag_utils.utils import get_cache_dir, infer_torch_device

from .base_embeddings import (
    DEFAULT_EMBED_BATCH_SIZE,
    BaseEmbedding,
)
from .pooling import Pooling
from .utils import format_query, format_text

if TYPE_CHECKING:
    import torch


def sliding_window_split(text, max_length=1204, stride=256, tokenizer=None):
    tokens = tokenizer.encode(text, truncation=False)
    chunks = []
    for i in range(0, len(tokens), stride):
        window = tokens[i:i + max_length]
        if not window:
            break
        chunks.append(tokenizer.decode(window, skip_special_tokens=True))
        if i + max_length >= len(tokens):
            break
    return chunks


class HuggingFaceEmbedding(BaseEmbedding):
    model_name: str = Field(default=DEFAULT_HUGGINGFACE_EMBEDDING_MODEL)
    tokenizer_name: Optional[str] = None
    pooling: Union[str, Pooling] = "cls"
    max_length: int = Field(default=512, gt=0)
    stride: int = Field(default=212, gt=0)
    sliding_window: bool = True
    normalize: bool = True
    embedding_batch_size: int = DEFAULT_EMBED_BATCH_SIZE
    token: Optional[str] = None
    cache_folder: Optional[str] = None
    trust_remote_code: bool = False
    query_instruction: Optional[str] = None
    text_instruction: Optional[str] = None
    device: str = Field(default_factory=infer_torch_device)

    _model: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.tokenizer_name:
            self.tokenizer_name = self.model_name
        if isinstance(self.pooling, str):
            self.pooling = Pooling(self.pooling)
        self._initialize_model()

    def _initialize_model(self):
        from transformers import AutoModel, AutoTokenizer
        self._model = AutoModel.from_pretrained(
            self.model_name,
            cache_dir=self.cache_folder or get_cache_dir(),
            trust_remote_code=self.trust_remote_code,
            token=self.token,
        ).to(self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.tokenizer_name,
            cache_dir=self.cache_folder or get_cache_dir()
        )

    def get_model_dim(self) -> int:
        return self._model.config.hidden_size

    @classmethod
    def class_name(cls) -> str:
        return "HuggingFaceEmbedding"

    def _mean_pooling(self, token_embeddings: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return (token_embeddings * input_mask_expanded).sum(1) / input_mask_expanded.sum(1).clamp(min=1e-9)

    def _embed(self, sentences: List[str]) -> List[List[float]]:
        import torch
        all_embeddings = []

        for idx, text in enumerate(sentences):
            tokens = self._tokenizer.encode(text, truncation=False)
            token_len = len(tokens)

            if self.sliding_window and token_len > self.max_length:
                # print(f"⚠️ _embed() → Texto {idx} tiene {token_len} tokens. Usando sliding window.")
                chunks = sliding_window_split(
                    text,
                    max_length=self.max_length,
                    stride=self.stride,
                    tokenizer=self._tokenizer
                )
                # print(f"🧩 Texto {idx} dividido en {len(chunks)} chunks (stride={self.stride})")
            else:
                # if token_len > self.max_length:
                    # print(f"⚠️ _embed() → Texto {idx} tiene {token_len} tokens. Truncando a {self.max_length} tokens.")
                chunks = [text]

            chunk_embeddings = []

            for i in range(0, len(chunks), self.embedding_batch_size):
                batch = chunks[i:i + self.embedding_batch_size]
                encoded_input = self._tokenizer(
                    batch,
                    padding=True,
                    max_length=self.max_length,
                    truncation=True,
                    return_tensors="pt",
                )
                encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
                model_output = self._model(**encoded_input)

                if self.pooling == Pooling.CLS:
                    embeddings = self.pooling.cls_pooling(model_output[0])
                else:
                    embeddings = self._mean_pooling(model_output[0], encoded_input["attention_mask"])

                if self.normalize:
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

                chunk_embeddings.extend(embeddings.cpu().tolist())

            # Promediar los embeddings de los chunks
            avg_embedding = torch.tensor(chunk_embeddings).mean(dim=0)
            all_embeddings.append(avg_embedding.tolist())

        return all_embeddings

    def _process_and_embed(self, texts: List[str]) -> List[List[float]]:

        final_embeddings = []

        for idx, text in enumerate(texts):
            # Formateo de entrada (puedes mover esto si ya viene formateado antes)
            tokens = self._tokenizer.encode(text, truncation=False)
            token_len = len(tokens)
            if token_len > self.max_length:

                chunks = sliding_window_split(
                    text,
                    max_length=self.max_length,
                    stride=self.stride,
                    tokenizer=self._tokenizer
                )
            else:
                chunks = [text]

            chunk_embeddings = self._embed(chunks)
            avg_embedding = torch.tensor(chunk_embeddings).mean(dim=0)
            final_embeddings.append(avg_embedding.tolist())

        return final_embeddings

    def _get_query_embedding(self, query: str) -> List[float]:
        formatted = format_query(query, self.model_name, self.query_instruction)
        return self._process_and_embed([formatted])[0]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        formatted = format_text(text, self.model_name, self.text_instruction)
        return self._process_and_embed([formatted])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        formatted_texts = [format_text(text, self.model_name, self.text_instruction) for text in texts]
        return self._process_and_embed(formatted_texts)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)
