from typing import Optional, List, Callable, Sequence

class PromptHelper:
    def __init__(
        self,
        tokenizer: Callable[[str], List[int]],
        context_window: int = 2048,
        max_input_size: Optional[int] = None,
        num_output: int = 512,
        chunk_overlap_ratio: float = 0.1,
    ):
        self.tokenizer = tokenizer
        self.context_window = context_window
        self.num_output = num_output
        self.max_input_size = max_input_size or (context_window - num_output)
        self.chunk_overlap_ratio = chunk_overlap_ratio

    def get_available_context_size(self) -> int:
        return self.max_input_size

    def __repr__(self):
        return (
            f"PromptHelper(context_window={self.context_window}, "
            f"max_input_size={self.max_input_size}, num_output={self.num_output})"
        )

    def repack(self, prompt_template, text_chunks: Sequence[str]) -> list[str]:
        """Divide los textos en bloques que quepan dentro del límite de tokens."""
        chunks = []
        current_chunk = ""

        for text in text_chunks:
            combined = current_chunk + text + "\n\n"
            if len(self.tokenizer(combined)) <= self.max_input_size:
                current_chunk = combined
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = text + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def truncate(
            self,
            text_chunks: List[str],
            prompt: Optional[str] = None,
            query_str: Optional[str] = None
    ) -> List[str]:
        prompt_str = str(prompt) if prompt is not None else ""
        query_str = str(query_str) if query_str is not None else ""

        prompt_tokens = self.tokenizer(prompt_str)
        query_tokens = self.tokenizer(query_str)
        total_tokens = len(prompt_tokens) + len(query_tokens)

        result = []
        for chunk in text_chunks:
            chunk_tokens = self.tokenizer(chunk)
            if total_tokens + len(chunk_tokens) <= self.max_input_size:
                result.append(chunk)
                total_tokens += len(chunk_tokens)
            else:
                break

        return result
