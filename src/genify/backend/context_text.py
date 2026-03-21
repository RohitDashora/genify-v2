"""Shared character limits for prompt context (limits come from app.yaml via config)."""


def truncate_chars(text: str, max_chars: int) -> str:
    """Return text truncated to max_chars with a suffix; max_chars <= 0 means no limit."""
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def tail_chars(text: str, max_chars: int) -> str:
    """Return the last max_chars of text; max_chars <= 0 means return full text."""
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]
