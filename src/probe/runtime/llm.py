"""Unified OpenAI-compatible LLM client.

Supports any provider with OpenAI-compat API: DashScope (Qwen), DeepSeek,
OpenAI, OpenRouter, local vLLM, etc. Single abstraction so downstream
components don't care which family they're calling.
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Sequence

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

log = logging.getLogger("probe.runtime.llm")


@dataclass
class ChatMessage:
    role: str
    content: str


_RETRYABLE = (APIConnectionError, RateLimitError)


@dataclass
class LLMClient:
    """Single-provider LLM client with explicit model family tag.

    `family` is used downstream to enforce judge-panel heterogeneity.
    """
    name: str                              # short label: "qwen-max", "claude-sonnet"
    family: str                            # "qwen" | "claude" | "deepseek" | "gpt" | ...
    model_id: str                          # actual model identifier for the API
    api_key: str
    base_url: str
    default_temperature: float = 0.3
    default_max_tokens: int = 1024
    max_retries: int = 4                   # total attempts = 1 + max_retries
    retry_base_delay: float = 1.0          # seconds, exponential
    retry_max_delay: float = 30.0
    # running totals; reset externally when needed
    total_prompt_tokens: int = field(default=0, init=False)
    total_completion_tokens: int = field(default=0, init=False)
    total_calls: int = field(default=0, init=False)
    _client: OpenAI | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: Sequence[ChatMessage | dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **extra,
    ) -> str:
        """Send chat completion with retry + token counting. Returns text."""
        assert self._client is not None
        msgs = [
            m if isinstance(m, dict) else {"role": m.role, "content": m.content}
            for m in messages
        ]
        temp = self.default_temperature if temperature is None else temperature
        mtk = self.default_max_tokens if max_tokens is None else max_tokens

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._client.chat.completions.create(
                    model=self.model_id, messages=msgs,
                    temperature=temp, max_tokens=mtk, **extra,
                )
                self.total_calls += 1
                if r.usage:
                    self.total_prompt_tokens += int(r.usage.prompt_tokens or 0)
                    self.total_completion_tokens += int(r.usage.completion_tokens or 0)
                return r.choices[0].message.content or ""
            except _RETRYABLE as e:
                last_err = e
                if attempt == self.max_retries:
                    break
                delay = min(
                    self.retry_max_delay,
                    self.retry_base_delay * (2 ** attempt) * (1 + 0.1 * random.random()),
                )
                log.warning("LLM %s attempt %d failed: %s — retry in %.1fs",
                            self.model_id, attempt + 1, type(e).__name__, delay)
                time.sleep(delay)
            except APIError as e:
                # non-retryable 4xx
                log.error("LLM %s non-retryable error: %s", self.model_id, e)
                raise
        assert last_err is not None
        raise last_err

    def usage_snapshot(self) -> dict:
        return dict(
            model=self.model_id, family=self.family,
            calls=self.total_calls,
            prompt_tokens=self.total_prompt_tokens,
            completion_tokens=self.total_completion_tokens,
        )

    # ---------------- factory helpers ----------------

    @classmethod
    def qwen(cls, model_id: str = "qwen3.6-plus", **kw) -> "LLMClient":
        return cls(
            name=model_id,
            family="qwen",
            model_id=model_id,
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            **kw,
        )

    @classmethod
    def deepseek(cls, model_id: str = "deepseek-chat", **kw) -> "LLMClient":
        return cls(
            name=model_id,
            family="deepseek",
            model_id=model_id,
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            **kw,
        )

    @classmethod
    def openai_compat(cls, name: str, family: str, model_id: str,
                      env_key: str, env_base: str, **kw) -> "LLMClient":
        return cls(
            name=name, family=family, model_id=model_id,
            api_key=os.environ[env_key],
            base_url=os.environ[env_base],
            **kw,
        )
