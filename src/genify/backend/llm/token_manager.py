"""Token counting, budget enforcement, and history trimming."""
import logging
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_tokenizer():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a string using tiktoken."""
    return len(_get_tokenizer().encode(text))


def count_messages_tokens(messages: list[dict]) -> int:
    """Count total tokens across all messages."""
    return sum(count_tokens(m.get("content", "")) for m in messages)


def fits_budget(messages: list[dict], max_tokens: int) -> bool:
    """Check if messages fit within the token budget."""
    return count_messages_tokens(messages) <= max_tokens


def trim_history(
    messages: list[dict],
    max_tokens: int,
    keep_recent: int = 4,
) -> list[dict]:
    """Trim conversation history to fit within a token budget.

    Strategy:
    1. Always keep system messages
    2. Always keep the most recent `keep_recent` messages
    3. Drop middle messages (oldest first) until under budget
    """
    if fits_budget(messages, max_tokens):
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= keep_recent:
        return messages

    recent = non_system[-keep_recent:]
    middle = non_system[:-keep_recent]

    system_tokens = count_messages_tokens(system_msgs)
    recent_tokens = count_messages_tokens(recent)
    remaining_budget = max_tokens - system_tokens - recent_tokens

    kept_middle = []
    for msg in reversed(middle):
        msg_tokens = count_tokens(msg.get("content", ""))
        if remaining_budget >= msg_tokens:
            kept_middle.insert(0, msg)
            remaining_budget -= msg_tokens
        else:
            break

    trimmed = system_msgs + kept_middle + recent
    dropped = len(messages) - len(trimmed)
    if dropped > 0:
        logger.info(f"Trimmed {dropped} messages to fit {max_tokens} token budget")
    return trimmed
