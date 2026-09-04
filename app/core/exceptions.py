class TriageError(Exception):
    """Base exception for all application errors."""


class LLMResponseError(TriageError):
    """LLM did not return a valid result after all retry attempts."""

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts
