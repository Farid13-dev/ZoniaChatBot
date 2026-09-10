import json

from rag.output_parser.base import BaseOutputParser
from rag.output_parser.types import StructuredOutput
from rag.question_gen.types import SubQuestion

class DefaultSubQuestionOutputParser(BaseOutputParser):
    def parse(self, text: str) -> StructuredOutput:
        try:
            # 🔍 Limpiar texto si viene envuelto en markdown o contiene caracteres basura
            text = text.strip()
            if text.startswith("```json"):
                text = text[len("```json"):].strip()
            if text.endswith("```"):
                text = text[:-3].strip()

            json_obj = json.loads(text)
            items = json_obj.get("items", [])
            subquestions = [SubQuestion(**item) for item in items]
            return StructuredOutput(parsed_output=subquestions, raw_output=text)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON subquestions: {e}")

    def format(self, prompt: str) -> str:
        return prompt
