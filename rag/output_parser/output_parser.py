from typing import Any

from rag.question_gen.types import SubQuestion  # ✅ NO desde base
from rag.output_parser.base import BaseOutputParser
from rag.output_parser.types import StructuredOutput
from rag.question_gen.utils import parse_json_markdown




class SubQuestionOutputParser(BaseOutputParser):
    def parse(self, output: str) -> Any:
        json_dict = parse_json_markdown(output)
        if not json_dict:
            raise ValueError(f"No valid JSON found in output: {output}")

        if not isinstance(json_dict, dict) or "items" not in json_dict:
            raise ValueError(f"Invalid JSON structure. Expected dict with 'items' key. Got: {json_dict}")

        sub_questions = [SubQuestion.parse_obj(item) for item in json_dict["items"]]
        return StructuredOutput(raw_output=output, parsed_output=sub_questions)

    def format(self, prompt_template: str) -> str:
        return prompt_template

