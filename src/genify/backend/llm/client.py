"""LLM client for Databricks Foundation Models API.

Ported from the original Genify app/llm/client.py — removed Streamlit
caching, uses @lru_cache instead. Keeps chat, streaming, token counting,
and error classification.
"""
import logging
import time
from functools import lru_cache
from typing import Generator

import tiktoken
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from backend.config import get_config

logger = logging.getLogger(__name__)


class LLMRateLimitError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


class LLMClient:
    """Client for calling Databricks LLM serving endpoints."""

    def __init__(self, endpoint_name: str, max_tokens: int, temperature: float):
        self.endpoint_name = endpoint_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.call_count = 0
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

        try:
            self.client = WorkspaceClient()
        except Exception as e:
            logger.error(f"Failed to initialize WorkspaceClient: {e}", exc_info=True)
            raise RuntimeError(f"Cannot initialize LLM client: {e}") from e

        logger.info(
            f"LLMClient initialized: endpoint={endpoint_name}, "
            f"max_tokens={max_tokens}, temp={temperature}"
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens accurately using tiktoken."""
        return len(self.tokenizer.encode(text))

    def chat(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send a chat request. Returns the response string."""
        self.call_count += 1
        call_id = self.call_count
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        total_input = sum(self.count_tokens(m["content"]) for m in messages)
        logger.info(
            f"[Call #{call_id}] LLM request: {self.endpoint_name}, "
            f"{len(messages)} msgs, {total_input:,} input tokens"
        )

        start = time.time()
        try:
            sdk_messages = [
                ChatMessage(role=ChatMessageRole(m["role"]), content=m["content"])
                for m in messages
            ]
            response = self.client.serving_endpoints.query(
                name=self.endpoint_name,
                messages=sdk_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            elapsed = time.time() - start
            content = response.choices[0].message.content or ""
            out_tokens = self.count_tokens(content)
            logger.info(
                f"[Call #{call_id}] response: {out_tokens:,} tokens in {elapsed:.2f}s"
            )
            return content

        except Exception as e:
            elapsed = time.time() - start
            self._classify_and_raise(call_id, elapsed, e)

    def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Stream chat response token by token."""
        self.call_count += 1
        call_id = self.call_count
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        total_input = sum(self.count_tokens(m["content"]) for m in messages)
        logger.info(
            f"[Call #{call_id}] LLM stream: {self.endpoint_name}, "
            f"{len(messages)} msgs, {total_input:,} input tokens"
        )

        start = time.time()
        full_response = ""
        try:
            sdk_messages = [
                ChatMessage(role=ChatMessageRole(m["role"]), content=m["content"])
                for m in messages
            ]
            response = self.client.serving_endpoints.query(
                name=self.endpoint_name,
                messages=sdk_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for chunk in response:
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        full_response += delta.content
                        yield delta.content

            elapsed = time.time() - start
            out_tokens = self.count_tokens(full_response)
            logger.info(
                f"[Call #{call_id}] stream complete: {out_tokens:,} tokens in {elapsed:.2f}s"
            )

        except Exception as e:
            elapsed = time.time() - start
            if full_response:
                logger.warning(
                    f"[Call #{call_id}] stream error after partial ({len(full_response)} chars)"
                )
            self._classify_and_raise(call_id, elapsed, e)

    def _classify_and_raise(self, call_id: int, elapsed: float, e: Exception):
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            logger.error(f"[Call #{call_id}] rate limit after {elapsed:.2f}s")
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e
        elif "timeout" in error_msg or "timed out" in error_msg:
            logger.error(f"[Call #{call_id}] timeout after {elapsed:.2f}s")
            raise LLMTimeoutError(f"Request timed out: {e}") from e
        else:
            logger.error(f"[Call #{call_id}] error after {elapsed:.2f}s: {e}")
            raise


@lru_cache(maxsize=1)
def get_main_llm_client() -> LLMClient:
    """Cached LLM client for the main interview endpoint (GPT-5.2)."""
    cfg = get_config().llm
    return LLMClient(cfg.endpoint_name, cfg.max_tokens, cfg.temperature)


@lru_cache(maxsize=1)
def get_summarizer_llm_client() -> LLMClient:
    """Cached LLM client for the summarizer endpoint (Gemini Flash)."""
    cfg = get_config().llm
    return LLMClient(
        cfg.summarizer_endpoint_name,
        cfg.summarizer_max_tokens,
        cfg.summarizer_temperature,
    )
