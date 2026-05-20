"""
WitchAgent — 女巫 Agent
拥有解药和毒药各一次；能看到当晚被刀目标；简单策略。
"""

from __future__ import annotations

from ..schemas.agent import AgentAction, AgentView
from .base import BaseAgent


class WitchAgent(BaseAgent):
    """女巫 Agent（简单启发式策略）"""

    def __init__(self, player_id: int, role: str = "witch", name: str = ""):
        super().__init__(player_id, role, name)

    def speak(self) -> AgentAction:
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
            content="我是村民。",
        )

    def decide_night_action(self) -> AgentAction:
        view = self._view
        if not view:
            return AgentAction(actor_id=self.player_id, action_type="witch_action")

        has_antidote = view.private_info.has_antidote
        has_poison = view.private_info.has_poison
        kill_target = view.private_info.tonight_kill_target

        use_save = False
        poison_target = None

        # 如果解药还在且有人被刀，救自己或其他人
        if has_antidote and kill_target is not None:
            use_save = True

        # 如果毒药还在，随机毒一个非狼人
        # Phase 2 不要求聪明，简单策略即可

        import json
        content = json.dumps({
            "use_save": use_save,
            "poison_target": poison_target,
        })

        return AgentAction(
            actor_id=self.player_id,
            action_type="witch_action",
            content=content,
        )

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
        return AgentAction(actor_id=self.player_id, action_type="hunter_shot")
