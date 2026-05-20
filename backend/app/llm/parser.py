"""
LLM 返回 JSON 解析器 — 将 LLM 输出转为 AgentAction。
"""
from __future__ import annotations

from typing import Any

from ..schemas.agent import AgentAction


class LLMParseError(Exception):
    """LLM 输出解析失败"""
    pass


def parse_llm_action(
    llm_output: dict[str, Any] | None,
    actor_id: int,
    legal_actions: list[str],
) -> AgentAction | None:
    """
    将 LLM 返回的 JSON dict 解析为 AgentAction。
    失败返回 None（由调用者决定 fallback）。
    """
    if llm_output is None:
        return None

    action_type = llm_output.get("action_type", "")
    if not isinstance(action_type, str) or action_type not in legal_actions:
        return None

    target_id = llm_output.get("target_id")
    if target_id is not None and not isinstance(target_id, int):
        try:
            target_id = int(target_id)
        except (ValueError, TypeError):
            target_id = None

    content = llm_output.get("content")
    if content is not None and not isinstance(content, str):
        content = str(content) if content else None

    reasoning = llm_output.get("reasoning_summary", "")

    return AgentAction(
        actor_id=actor_id,
        action_type=action_type,
        target_id=target_id,
        content=content,
        metadata={
            "source": "llm",
            "reasoning_summary": str(reasoning)[:50] if reasoning else "",
        },
    )
