import logging
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.core.config import settings
from app.core.exceptions import LLMResponseError
from app.prompts.triage import REPAIR_TEMPLATE, SYSTEM_INSTRUCTION, build_user_prompt
from app.schemas.input.inbox_request import InboxRequest
from app.schemas.output.triage_result import TriageResult

logger = logging.getLogger(__name__)

MARKDOWN_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")

# Configuration errors: retrying won't help, fail immediately.
FATAL_STATUS_CODES = {400, 401, 403, 404}


def strip_markdown_fence(text: str) -> str:
    """Remove ```json ... ``` wrappers the model adds even when told not to."""
    return MARKDOWN_FENCE.sub("", text).strip()


def format_validation_errors(exc: ValidationError) -> str:
    """Convert Pydantic errors into a list the model can understand and fix."""
    lines = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "(root)"
        lines.append(f"- field '{field}': {err['msg']}")
    return "\n".join(lines)


class GeminiTriageClient:
    """Gemini wrapper: send request, validate response, retry with self-correction."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self._model = model or settings.gemini_model
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=TriageResult,
            temperature=settings.temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def classify(self, request: InboxRequest) -> tuple[TriageResult, int]:
        """Return the classification result and the number of attempts used."""
        contents: list[str] = [build_user_prompt(request)]
        last_error = "unknown error"
        total_attempts = settings.max_retries + 1

        for attempt in range(1, total_attempts + 1):
            try:
                raw = self._generate(contents)
            except genai_errors.APIError as exc:
                if exc.code in FATAL_STATUS_CODES:
                    raise LLMResponseError(f"API error: {exc.code}", attempt) from exc
                last_error = f"API unavailable: {exc.code}"
                logger.warning("%s: attempt %s — %s", request.id, attempt, last_error)
                self._wait_before_retry(attempt)
                continue

            if not raw:
                last_error = "model returned an empty response"
                logger.warning("%s: attempt %s — %s", request.id, attempt, last_error)
                self._wait_before_retry(attempt)
                continue

            try:
                return TriageResult.model_validate_json(strip_markdown_fence(raw)), attempt
            except ValidationError as exc:
                last_error = format_validation_errors(exc)
                logger.warning(
                    "%s: attempt %s — validation failed:\n%s",
                    request.id,
                    attempt,
                    last_error,
                )
                contents = [
                    build_user_prompt(request),
                    raw,
                    REPAIR_TEMPLATE.format(errors=last_error),
                ]

        raise LLMResponseError(last_error, total_attempts)

    def _generate(self, contents: list[str]) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=self._config,
        )
        return response.text or ""

    @staticmethod
    def _wait_before_retry(attempt: int) -> None:
        """Exponential backoff: retrying immediately on 429 just burns quota."""
        time.sleep(settings.retry_backoff_seconds * 2 ** (attempt - 1))
