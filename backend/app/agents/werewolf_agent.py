"""
WerewolfAgent — 狼人 Agent
夜晚击杀非狼人存活目标；发言伪装；投票优先投非狼人。
"""

from __future__ import annotations

import random

from ..schemas.agent import AgentAction, AgentView
from .base import BaseAgent


class WerewolfAgent(BaseAgent):
    """狼人 Agent（简单启发式策略）"""

    def __init__(self, player_id: int, role: str = "werewolf", name: str = ""):
        super().__init__(player_id, role, name)

    def speak(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="speak")

        wolves = set(view.private_info.known_wolves) | {self.player_id}
        # 编造一个好人发言
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
            content="我是村民，目前没什么信息，跟大家一起投票。",
        )

    def decide_night_action(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="werewolf_kill")

        wolves = set(view.private_info.known_wolves) | {self.player_id}
        targets = [
            p for p in view.public_players
            if p.alive and p.player_id not in wolves
        ]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="werewolf_kill")

        target = random.choice(targets)
        return AgentAction(
            actor_id=self.player_id,
            action_type="werewolf_kill",
            target_id=target.player_id,
        )

    def decide_vote(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="vote")

        wolves = set(view.private_info.known_wolves) | {self.player_id}
        targets = [
            p for p in view.public_players
            if p.alive and p.player_id not in wolves
        ]
        if not targets:
            return AgentAction(actor_id=self.player_id, action_type="vote")

        return AgentAction(
            actor_id=self.player_id,
            action_type="vote",
            target_id=random.choice(targets).player_id,
        )

    def decide_hunter_shot(self) -> AgentAction:
        return AgentAction(actor_id=self.player_id, action_type="hunter_shot")
