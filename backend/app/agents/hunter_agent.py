"""
HunterAgent — 猎人 Agent
死亡时可开枪带走一人；白天正常发言投票。
"""

from __future__ import annotations

from ..schemas.agent import AgentAction, AgentView
from .base import BaseAgent


class HunterAgent(BaseAgent):
    """猎人 Agent（简单启发式策略）"""

    def __init__(self, player_id: int, role: str = "hunter", name: str = ""):
        super().__init__(player_id, role, name)

    def speak(self) -> AgentAction:
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
            content="我是村民。",
        )

    def decide_night_action(self) -> AgentAction:
        return AgentAction(actor_id=self.player_id, action_type="skip")

    def decide_vote(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="vote")
        targets = [
            p for p in view.public_players
            if p.alive and p.player_id != self.player_id
        ]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="vote")
        return AgentAction(
            actor_id=self.player_id,
            action_type="vote",
            target_id=targets[0].player_id,
        )

    def decide_hunter_shot(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="hunter_shot")
        targets = [
            p for p in view.public_players
            if p.alive and p.player_id != self.player_id
        ]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="hunter_shot")
        return AgentAction(
            actor_id=self.player_id,
            action_type="hunter_shot",
            target_id=targets[0].player_id,
        )
