"""
SeerAgent — 预言家 Agent
夜晚查验未查过的存活玩家；记录结果；投票优先投已知狼人。
"""

from __future__ import annotations

import random

from ..schemas.agent import AgentAction, AgentView, InvestigationResult
from .base import BaseAgent


class SeerAgent(BaseAgent):
    """预言家 Agent（简单启发式策略）"""

    def __init__(self, player_id: int, role: str = "seer", name: str = ""):
        super().__init__(player_id, role, name)

    def speak(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="speak")
        # 简单发言：声称村民
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
            content="我是村民。",
        )

    def decide_night_action(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="seer_investigate")

        # 找出已查过的玩家
        investigated_ids = {r.target_id for r in view.private_info.investigation_results}
        # 找存活且未查过的玩家（不能查自己）
        targets = [
            p for p in view.public_players
            if p.alive and p.player_id not in investigated_ids
            and p.player_id != self.player_id
        ]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="seer_investigate")

        target = random.choice(targets)
        return AgentAction(
            actor_id=self.player_id,
            action_type="seer_investigate",
            target_id=target.player_id,
        )

    def decide_vote(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="vote")

        # 优先投已知狼人
        known_wolves = {
            r.target_id for r in view.private_info.investigation_results
            if r.is_werewolf
        }
        wolf_alive = [
            p for p in view.public_players
            if p.alive and p.player_id in known_wolves
        ]
        if wolf_alive:
            return AgentAction(
                actor_id=self.player_id,
                action_type="vote",
                target_id=wolf_alive[0].player_id,
            )

        # 没有已知狼人，投第一个存活玩家
        targets = [p for p in view.public_players if p.alive and p.player_id != self.player_id]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="vote")
        return AgentAction(
            actor_id=self.player_id,
            action_type="vote",
            target_id=targets[0].player_id,
        )

    def decide_hunter_shot(self) -> AgentAction:
        return AgentAction(actor_id=self.player_id, action_type="hunter_shot")
