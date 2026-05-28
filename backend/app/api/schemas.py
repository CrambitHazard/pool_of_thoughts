"""API request and response schemas."""

from pydantic import BaseModel, Field

from app.cognitive.thought_extraction import ThoughtExtractionResult


class UserMessageInput(BaseModel):
    """Raw user message submitted for cognition parsing."""

    message: str = Field(min_length=1, max_length=4000)


class ThoughtExtractionResponse(ThoughtExtractionResult):
    """Structured thought extraction returned to clients."""

    pass
