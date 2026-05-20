"""
BaseAgent — 所有角色 Agent 的统一抽象接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas.agent import AgentAction, AgentView


class BaseAgent(ABC):
    """
    角色 Agent 基类。
    所有具体角色 Agent 必须实现 speak / decide_night_action / decide_vote / decide_hunter_shot。
    """

    def __init__(self, player_id: int, role: str, name: str = ""):
        self.player_id = player_id
        self.role = role
        self.name = name
        self._view: AgentView | None = None

    # ── 视角注入 ─────────────────────────────────────────

    def receive_view(self, view: AgentView) -> None:
        """接收当前 AgentView（信息隔离后的私有视角）"""
        self._view = view

    def get_view(self) -> AgentView | None:
        return self._view

    # ── 决策接口 ─────────────────────────────────────────

    def speak(self) -> AgentAction:
        """白天发言。默认返回空发言。"""
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
        )

    def decide_night_action(self) -> AgentAction:
        """夜晚决策。无特殊能力的角色返回 skip。"""
        return AgentAction(
            actor_id=self.player_id,
            action_type="skip",
        )

    def decide_vote(self) -> AgentAction:
        """白天投票决策。"""
        return AgentAction(
            actor_id=self.player_id,
            action_type="vote",
        )

    def decide_hunter_shot(self) -> AgentAction:
        """猎人开枪决策。默认不开枪。"""
        return AgentAction(
            actor_id=self.player_id,
            action_type="hunter_shot",
        )
