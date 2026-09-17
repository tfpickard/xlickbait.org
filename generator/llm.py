"""Ask Claude for a headline, and insist on getting one back in the right shape.

Uses the SDK's structured output (`messages.parse` with a Pydantic model), which
constrains the response to the schema. That removes the malformed-JSON failure
mode almost entirely -- the retry that remains is for API errors, not parsing.

Structured output says nothing about whether the `anchor` is real. That is the
truth gate's job, it is a different and much harder check, and it stays separate.
"""

from __future__ import annotations

from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

PROMPT_PATH = Path(__file__).parent / "prompts" / "headline_system.md"


class Headline(BaseModel):
    """The shape the model must return."""

    headline: str = Field(description="The front-page headline.")
    dek: str = Field(description="One sentence doubling down on the wrong angle.")
    anchor: str = Field(
        description=(
            "The exact span of the title or abstract containing the detail the "
            "headline ran with, copied character for character."
        )
    )
    actual_point: str = Field(
        description="One flat, honest sentence about what the paper really does."
    )


def load_system_prompt() -> str:
    """Read the style guide from disk.

    Kept in a file rather than a string literal so it can be edited, reviewed and
    diffed as prose -- it is the voice of the site, not configuration.
    """
    return PROMPT_PATH.read_text(encoding="utf-8")


def _user_message(title: str, abstract: str, categories: list[str]) -> str:
    return f"Title: {title}\n\nCategories: {', '.join(categories)}\n\nAbstract: {abstract}"


class HeadlineWriter:
    """Wraps the Anthropic client with this project's prompt and retry policy."""

    def __init__(self, *, api_key: str, model: str, max_retries: int = 2) -> None:
        # The SDK already retries connection errors, 408, 409, 429 and 5xx with
        # exponential backoff; max_retries here is that knob, not a second loop.
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)
        self._model = model
        self._system = load_system_prompt()

    def write(
        self,
        *,
        title: str,
        abstract: str,
        categories: list[str],
        retry_note: str | None = None,
    ) -> Headline:
        """Generate one headline.

        `retry_note` is appended when a previous attempt failed the truth gate, so
        the model is told what went wrong rather than simply asked again.
        """
        content = _user_message(title, abstract, categories)
        if retry_note:
            content += f"\n\n---\n\n{retry_note}"

        response = self._client.messages.parse(
            model=self._model,
            max_tokens=2000,
            system=self._system,
            messages=[{"role": "user", "content": content}],
            output_format=Headline,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("the model returned no parseable output")
        return parsed


RETRY_NOTE = (
    "Your previous attempt was rejected. The `anchor` you returned does not "
    "appear verbatim in the title or abstract above.\n\n"
    "Rejected anchor: {anchor!r}\n\n"
    "Copy the span character for character from the text above. Do not fix its "
    "punctuation, do not change its quotation marks or dashes, do not paraphrase "
    "it, and do not join text from two separate places. Pick a shorter span if "
    "that makes it easier to copy exactly."
)
