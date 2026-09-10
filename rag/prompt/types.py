"""Prompt types enum."""

from enum import Enum


class PromptType(str, Enum):
    """Prompt type."""

    # summarization
    SUMMARY = "summary"
    # tree insert node
    TREE_INSERT = "insert"
    # tree select query prompt
    TREE_SELECT = "tree_select"
    # tree select query prompt (multiple)
    TREE_SELECT_MULTIPLE = "tree_select_multiple"
    # question-answer
    QUESTION_ANSWER = "text_qa"
    # refine
    REFINE = "refine"
    # keyword extract
    KEYWORD_EXTRACT = "keyword_extract"
    # query keyword extract
    QUERY_KEYWORD_EXTRACT = "query_keyword_extract"

    # Simple Input prompt
    SIMPLE_INPUT = "simple_input"

    # Pandas prompt
    PANDAS = "pandas"

    # JSON path prompt
    JSON_PATH = "json_path"

    # Sub question prompt
    SUB_QUESTION = "sub_question"

    # SQL response synthesis prompt
    SQL_RESPONSE_SYNTHESIS = "sql_response_synthesis"

    # SQL response synthesis prompt (v2)
    SQL_RESPONSE_SYNTHESIS_V2 = "sql_response_synthesis_v2"

    # Conversation
    CONVERSATION = "conversation"

    # Decompose query transform
    DECOMPOSE = "decompose"

    # Choice select
    CHOICE_SELECT = "choice_select"

    # custom (by default)
    CUSTOM = "custom"
