"""
LLM 配置 — 从环境变量读取，默认关闭。
不依赖 python-dotenv。
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


class LLMConfig:
    """LLM 配置，从环境变量读取"""

    def __init__(self):
        self.enabled = os.getenv("LLM_ENABLED", "").lower() in ("true", "1", "yes")
        self.provider = os.getenv("LLM_PROVIDER", "openai_compatible")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "1"))

        if self.enabled and not self.api_key:
            logger.warning("LLM_ENABLED=true but LLM_API_KEY is empty — falling back to heuristic agent")
            self.enabled = False

    def is_available(self) -> bool:
        """LLM 是否可用（开启且有 API key）"""
        return self.enabled and bool(self.api_key)


def get_config() -> LLMConfig:
    """获取单例配置"""
    return LLMConfig()
