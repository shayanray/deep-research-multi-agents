"""
LLM utility: returns a configured ChatModel.

Priority order:
  1. NVIDIA_MODEL Llama 3.1 70B (NVIDIA_API_KEY)
  2. Anthropic Claude  (ANTHROPIC_API_KEY)
  2. OpenAI GPT-4o     (OPENAI_API_KEY)
  3. Raises RuntimeError with instructions.

Usage
-----
    from llm import get_llm
    llm = get_llm()
    response = llm.invoke("Hello")
"""
from __future__ import annotations

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.1):
    """Return a cached ChatModel instance."""
    nvidia_standard_llm = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
            return ChatNVIDIA(model=nvidia_standard_llm, temperature=temperature)
        except ImportError:
            logger.warning("langchain-nvidia-ai-endpoints not installed")

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Using Anthropic Claude (claude-3-5-sonnet-20241022)")
            return ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=temperature,
                max_tokens=4096,
                anthropic_api_key=anthropic_key,
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed; falling back to OpenAI")

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            logger.info("Using OpenAI GPT-4o")
            return ChatOpenAI(
                model="gpt-4o",
                temperature=temperature,
                openai_api_key=openai_key,
            )
        except ImportError:
            logger.warning("langchain-openai not installed")

    raise RuntimeError(
        "No LLM provider found.\n"
        "Set ANTHROPIC_API_KEY  — or —  OPENAI_API_KEY in your environment (or .env file)."
    )


def get_fast_llm(temperature: float = 0.0):
    """Lighter/faster model for classification tasks."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    nvidia_fast_llm = os.getenv("NVIDIA_FAST_MODEL", "meta/llama-3.1-70b-instruct")

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-3-haiku-20240307",
                temperature=temperature,
                max_tokens=1024,
                anthropic_api_key=anthropic_key,
            )
        except ImportError:
            pass

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=temperature,
                              openai_api_key=openai_key)
        except ImportError:
            pass
    
    if nvidia_key:
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
            return ChatNVIDIA(model=nvidia_fast_llm, temperature=temperature)
        except ImportError:
            pass

    return get_llm(temperature)
