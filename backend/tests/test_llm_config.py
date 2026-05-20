"""
LLM 配置测试 — 默认关闭，无 API key 时自动 fallback。
所有测试离线运行，不调用真实 API。
"""
import os

from backend.app.llm.config import LLMConfig, get_config


class TestLLMConfigDefault:
    """LLM 默认行为测试"""

    def test_llm_disabled_by_default(self):
        config = LLMConfig()
        assert not config.enabled, "LLM should be disabled by default"
        assert not config.is_available()

    def test_llm_disabled_when_api_key_missing(self):
        os.environ["LLM_ENABLED"] = "true"
        os.environ["LLM_API_KEY"] = ""
        config = LLMConfig()
        assert not config.is_available(), "Should not be available without API key"
        os.environ.pop("LLM_ENABLED", None)

    def test_llm_available_with_key(self):
        os.environ["LLM_ENABLED"] = "true"
        os.environ["LLM_API_KEY"] = "sk-test-key"
        config = LLMConfig()
        assert config.is_available()
        os.environ.pop("LLM_ENABLED", None)
        os.environ.pop("LLM_API_KEY", None)

    def test_llm_config_defaults(self):
        config = LLMConfig()
        assert config.provider == "openai_compatible"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o-mini"
        assert config.timeout_seconds == 20
        assert config.max_retries == 1
