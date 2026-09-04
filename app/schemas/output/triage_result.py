from enum import Enum

from pydantic import BaseModel, Field, field_validator

NO_VALUE_TOKENS = {"", "null", "none", "n/a", "-", "невідомо", "не зрозуміло", "не вказано"}

SUMMARY_MAX_LENGTH = 250


class Category(str, Enum):
    AUTOMATION = "автоматизація"
    INTEGRATION = "інтеграція"
    ANALYTICS = "звіт/аналітика"
    BUG = "баг/підтримка"
    QUESTION = "питання/консультація"
    OUT_OF_SCOPE = "поза скоупом"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TriageResult(BaseModel):
    """LLM contract: exactly what the model must return for one request."""

    category: Category
    target_department: str | None = None
    priority: Priority
    short_summary: str = Field(min_length=1, max_length=SUMMARY_MAX_LENGTH)
    requested_actions: list[str] = Field(default_factory=list)
    needs_clarification: bool

    is_actionable: bool
    confidence: float = Field(ge=0.0, le=1.0)
    deadline_mentioned: str | None = None
    clarification_question: str | None = None

    @field_validator("target_department", "deadline_mentioned", "clarification_question")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        """Normalize 'не зрозуміло', 'null', '-' etc. to real None."""
        if value is None:
            return None
        cleaned = value.strip()
        return None if cleaned.lower() in NO_VALUE_TOKENS else cleaned

    @field_validator("requested_actions")
    @classmethod
    def clean_actions(cls, actions: list[str]) -> list[str]:
        """Remove empty strings and duplicates while preserving order."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for action in actions:
            item = action.strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                cleaned.append(item)
        return cleaned
