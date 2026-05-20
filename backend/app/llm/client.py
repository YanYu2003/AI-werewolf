"""
OpenAI-compatible Chat Completions 客户端。
支持通过环境变量配置 base_url 以兼容任何 OpenAI-compatible API。
"""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

from .config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI-compatible Chat Completions 客户端"""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete_json(
        self,
        messages: list[dict],
        timeout: int | None = None,
    ) -> dict | None:
        """
        调用 Chat Completions API，返回解析后的 JSON dict。
        失败、超时、非法 JSON 均返回 None。
        """
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        actual_timeout = timeout if timeout is not None else self.config.timeout_seconds

        try:
            with urllib.request.urlopen(req, timeout=actual_timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.warning("LLM HTTP error: %s %s", e.code, e.reason)
            return None
        except urllib.error.URLError as e:
            logger.warning("LLM URL error: %s", str(e.reason))
            return None
        except json.JSONDecodeError:
            logger.warning("LLM response JSON decode failed")
            return None
        except TimeoutError:
            logger.warning("LLM request timed out after %ss", actual_timeout)
            return None
        except Exception as e:
            logger.warning("LLM request failed: %s", str(e))
            return None

        # 提取 content
        try:
            choice = resp_data["choices"][0]
            content = choice["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as e:
            logger.warning("LLM response parse failed: %s", str(e))
            return None


def create_llm_client(config: LLMConfig | None = None) -> LLMClient | None:
    """创建 LLM 客户端，如果配置不可用则返回 None"""
    if config is None:
        from .config import get_config
        config = get_config()
    if not config.is_available():
        return None
    return LLMClient(config)
