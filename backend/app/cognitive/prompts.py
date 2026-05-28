"""Deterministic prompts for internal cognition tasks."""

EXTRACTION_SYSTEM_PROMPT = """You are the internal cognition parser for AttentionOS.
Convert input into structured thought data.
Output valid JSON only.
Do not greet, explain, or use conversational language.
Keep each thought content concise and factual.
Use numeric scores between 0.0 and 1.0."""


def build_extraction_prompt(message: str, max_related: int) -> str:
    """Build the user prompt for thought extraction.

    Args:
        message: Raw user input text.
        max_related: Maximum related thoughts to request.

    Returns:
        str: Deterministic extraction prompt.
    """
    return f"""Parse the input into structured thoughts.

Input:
{message.strip()}

Return JSON with exactly these keys:
- primary_thought: object with content, salience, emotional_weight, novelty
- summary: one concise sentence, max 16 words
- related_thoughts: array of up to {max_related} objects with content, salience, emotional_weight, novelty

Rules:
- primary_thought.content captures the main cognitive focus
- summary compresses the primary thought
- related_thoughts are plausible follow-on ideas, not duplicates
- no markdown, no prose outside JSON"""
