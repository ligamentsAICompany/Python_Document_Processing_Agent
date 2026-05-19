"""Normalize LLM / JSON field content to plain strings (Gemini returns lists)."""

from __future__ import annotations


def content_to_str(value: object) -> str:
    """Coerce AIMessage.content, stream chunks, or node text fields to str."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for block in value:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text is not None:
                    parts.append(content_to_str(text))
            elif block is not None:
                parts.append(str(block))
        return "".join(parts)
    return str(value)
