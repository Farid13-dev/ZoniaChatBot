from pydantic import BaseModel
from typing import List, Sequence, TYPE_CHECKING, Optional

class SubQuestion(BaseModel):
    sub_question: str
    tool_name: Optional[str] = None  # <-- Esto es clave


class SubQuestionList(BaseModel):
    """A pydantic object wrapping a list of sub-questions.

    This is mostly used to make getting a json schema easier.
    """

    items: List[SubQuestion]

class JointAnswer(BaseModel):
    answer: str
    items: List[SubQuestion]
