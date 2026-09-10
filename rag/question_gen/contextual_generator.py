from typing import List, Optional, cast, TYPE_CHECKING

from rag.prompt.types import PromptType
from rag.prompt.prompt_template import PromptTemplate
from rag.output_parser.types import StructuredOutput
from rag.output_parser.output_parser import SubQuestionOutputParser
from rag.question_gen.types import SubQuestion

if TYPE_CHECKING:
    from rag.llm.base import LLM
    from rag.core.service_context import ServiceContext
    from rag.prompt.base_prompt import BasePromptTemplate
    from rag.output_parser.base import BaseOutputParser
    from rag.prompt.mixin import PromptDictType


class ContextualQuestionGenerator:
    def __init__(
            self,
            llm: "LLM",
            prompt: "BasePromptTemplate",
            max_subquestions: int = 3
    ) -> None:
        self._llm = llm
        self._prompt = prompt
        self._max_subquestions = max_subquestions
        if self._prompt.output_parser is None:
            raise ValueError("Prompt should have output parser.")

    @classmethod
    def from_defaults(
            cls,
            service_context: "ServiceContext" = None,
            prompt_template_str: Optional[str] = None,
            output_parser: "BaseOutputParser" = None,
            max_subquestions: int = 3,
    ) -> "ContextualQuestionGenerator":
        prompt_template_str = prompt_template_str or "Dado el contexto: {context} y la pregunta: {query}, genera subpreguntas..."
        output_parser = output_parser or SubQuestionOutputParser()

        prompt = PromptTemplate(
            template=prompt_template_str,
            output_parser=output_parser,
            prompt_type=PromptType.SUB_QUESTION,
        )
        return cls(service_context.llm, prompt, max_subquestions=max_subquestions)

    def _get_prompts(self) -> "PromptDictType":
        return {"question_gen_prompt": self._prompt}

    def _update_prompts(self, prompts: "PromptDictType") -> None:
        if "question_gen_prompt" in prompts:
            self._prompt = prompts["question_gen_prompt"]

    def generate(
            self, context_str: str, query_str: str
    ) -> List[SubQuestion]:
        prediction = self._llm.predict(
            prompt=self._prompt,
            context_str=context_str,
            query_str=query_str,
            max_subquestions=self._max_subquestions  #
        )

        assert self._prompt.output_parser is not None
        parsed = self._prompt.output_parser.parse(prediction)
        parsed = cast(StructuredOutput, parsed)
        return parsed.parsed_output

    async def agenerate(
            self, context: str, query: str
    ) -> List[SubQuestion]:
        prediction = await self._llm.apredict(
            prompt=self._prompt,
            context=context,
            query=query,
            max_subquestions=self._max_subquestions
        )

        assert self._prompt.output_parser is not None
        parsed = self._prompt.output_parser.parse(prediction)
        parsed = cast(StructuredOutput, parsed)
        return parsed.parsed_output
