"""
Fallback 逻辑 — LLM 不可用、超时、解析失败时的回退策略。
"""
from __future__ import annotations

import logging

from ..schemas.agent import AgentAction

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """封装各种 fallback 策略，所有方法都返回 AgentAction | None"""

    @staticmethod
    def heuristic_action(
        agent, method: str, view, legal_actions: list[str],
    ) -> AgentAction | None:
        """
        调用启发式 Agent 的对应方法获取动作。
        如果启发式 Agent 也失败，返回 None。
        """
        try:
            agent.receive_view(view)
            action = getattr(agent, method)()
            # 标记来源
            if action and action.metadata is not None:
                action.metadata["source"] = "heuristic"
            elif action:
                import copy
                action = copy.replace(action, metadata={"source": "heuristic"})
            return action
        except Exception as e:
            logger.warning("Heuristic agent fallback failed: %s", str(e))
            return None

    @staticmethod
    def safe_skip(actor_id: int) -> AgentAction | None:
        """绝对安全的跳过动作（不执行任何操作）"""
        return None

    @staticmethod
    def build_skip_action(
        actor_id: int, role: str, action_type: str = "skip",
    ) -> AgentAction:
        """构建一个明确的跳过动作"""
        return AgentAction(
            actor_id=actor_id,
            action_type=action_type,
            target_id=None,
            content=None,
            metadata={"source": "fallback_skip"},
        )
