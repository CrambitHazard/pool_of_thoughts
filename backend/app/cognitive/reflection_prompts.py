"""Deterministic prompts for reflective consolidation."""

REFLECTION_SYSTEM_PROMPT = """You are the internal reflection engine for AttentionOS.
Compress related episodic thoughts into one semantic memory.
Output valid JSON only.
Do not greet, explain, or use conversational language.
Write summaries as durable observations, not quotes of individual events."""


def build_abstraction_prompt(thoughts: list[str], theme_hint: str) -> str:
    """Build the user prompt for semantic memory abstraction.

    Args:
        thoughts: Recent thought contents in a recurring cluster.
        theme_hint: Heuristic theme label from local analysis.

    Returns:
        str: Deterministic abstraction prompt.
    """
    bullet_lines = "\n".join(f"- {content.strip()}" for content in thoughts)
    return f"""Review these related recent thoughts and compress them into one semantic memory.

Theme hint:
{theme_hint.strip()}

Recent thoughts:
{bullet_lines}

Return JSON with exactly these keys:
- summary: one concise sentence capturing the recurring pattern
- theme: short theme label
- confidence: number from 0.0 to 1.0 indicating consolidation confidence

Rules:
- summary must generalize across all listed thoughts
- avoid repeating exact wording from a single thought
- no markdown, no prose outside JSON"""
