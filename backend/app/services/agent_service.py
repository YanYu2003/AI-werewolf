"""
AgentService — Agent 编排层

负责在游戏引擎和 Agent 之间搭建桥梁：
1. 为每个 Agent 构建 AgentView（信息隔离）
2. 调用 Agent 决策方法
3. 校验动作合法性
4. 提交动作到引擎
5. 处理 fallback
"""

from __future__ import annotations

import json
import random
from typing import Dict, List, Optional

from ..agents.base import BaseAgent
from ..agents.factory import create_agents_for_game
from ..engine.action_validator import validate_agent_action
from ..engine.game_engine import WerewolfGameEngine
from ..engine.visibility import build_agent_view
from ..schemas.agent import AgentAction
from ..schemas.models import (
    DayStage,
    GamePhase,
    NightStage,
    Role,
    Team,
)


class AgentService:
    """
    Agent 编排服务。
    管理一局游戏中所有 Agent 的生命周期和决策流程。
    """

    def __init__(
        self,
        engine: WerewolfGameEngine,
        agents: Optional[Dict[int, BaseAgent]] = None,
    ):
        self.engine = engine
        self.agents = agents or {}

        # 如果没有传入 agents，自动创建
        if not self.agents and engine.players:
            self.agents = create_agents_for_game(engine.players)  # type: ignore

    # ── 核心编排 ─────────────────────────────────────────

    def run_full_game(self) -> Dict:
        """
        自动运行一局完整游戏。
        返回游戏结束时的日志数据。
        """
        max_rounds = 20
        for _ in range(max_rounds):
            if self.engine.phase == GamePhase.ENDED:  # type: ignore
                break

            # 夜晚
            self._run_night_phase()

            if self.engine.phase == GamePhase.ENDED:  # type: ignore
                break

            # 白天
            self._run_day_phase()

        log = self.engine.get_log()  # type: ignore
        return log.model_dump()

    # ── 夜晚编排 ─────────────────────────────────────────

    def _run_night_phase(self) -> None:
        """运行完整的夜晚阶段"""
        # 狼人阶段
        if self.engine.night_stage == NightStage.WEREWOLF_KILL:  # type: ignore
            self._run_werewolf_night()

        if self.engine.phase == GamePhase.ENDED:  # type: ignore
            return

        # 预言家阶段
        if self.engine.night_stage == NightStage.SEER_INVESTIGATE:  # type: ignore
            self._run_seer_night()

        if self.engine.phase == GamePhase.ENDED:  # type: ignore
            return

        # 女巫阶段
        if self.engine.night_stage == NightStage.WITCH_ACTION:  # type: ignore
            self._run_witch_night()

    def _run_werewolf_night(self) -> None:
        """狼人夜晚行动"""
        wolves = self._get_alive_agents_by_role(Role.WEREWOLF)
        if not wolves:
            return

        # 先收集所有狼人的目标（他们相互可见，应能协调）
        # Phase 2 简单实现：每个狼人独立投票
        for agent in wolves:
            if agent.player_id not in self.agents:
                continue
            self._agent_decide_and_submit(
                agent,
                "decide_night_action",
                expected_stage=NightStage.WEREWOLF_KILL,
            )

    def _run_seer_night(self) -> None:
        """预言家夜晚行动"""
        seer = self._get_alive_agent_by_role(Role.SEER)
        if seer is None:
            return
        self._agent_decide_and_submit(
            seer,
            "decide_night_action",
            expected_stage=NightStage.SEER_INVESTIGATE,
        )

    def _run_witch_night(self) -> None:
        """女巫夜晚行动"""
        witch = self._get_alive_agent_by_role(Role.WITCH)
        if witch is None:
            return
        self._agent_decide_and_submit(
            witch,
            "decide_night_action",
            expected_stage=NightStage.WITCH_ACTION,
        )

    # ── 白天编排 ─────────────────────────────────────────

    def _run_day_phase(self) -> None:
        """运行完整的白天阶段"""
        # 猎人夜晚死亡开枪
        if self.engine.day_stage == DayStage.JUDGMENT:  # type: ignore
            self._run_hunter_shot()

        if self.engine.phase == GamePhase.ENDED:  # type: ignore
            return

        # 发言
        if self.engine.day_stage == DayStage.SPEAK:  # type: ignore
            self._run_speak_phase()

        if self.engine.phase == GamePhase.ENDED:  # type: ignore
            return

        # 投票
        if self.engine.day_stage == DayStage.VOTE:  # type: ignore
            self._run_vote_phase()

        if self.engine.phase == GamePhase.ENDED:  # type: ignore
            return

        # 猎人放逐开枪
        if self.engine.day_stage == DayStage.JUDGMENT:  # type: ignore
            self._run_hunter_shot()

    def _run_speak_phase(self) -> None:
        """发言阶段：所有存活玩家依次发言"""
        alive = [p for p in self.engine.players if p.alive]  # type: ignore
        for p in alive:
            agent = self.agents.get(p.id)
            if agent is None:
                continue
            if self.engine.day_stage != DayStage.SPEAK:  # type: ignore
                break
            self._agent_decide_and_submit(
                agent,
                "speak",
                expected_stage=DayStage.SPEAK,
            )

    def _run_vote_phase(self) -> None:
        """投票阶段"""
        retries = 0
        while self.engine.day_stage == DayStage.VOTE and retries < 20:  # type: ignore
            alive = [p for p in self.engine.players if p.alive]  # type: ignore
            for p in alive:
                agent = self.agents.get(p.id)
                if agent is None:
                    continue
                if self.engine.day_stage != DayStage.VOTE:  # type: ignore
                    break
                if p.id in self.engine.day_votes:  # type: ignore
                    continue
                self._agent_decide_and_submit(
                    agent,
                    "decide_vote",
                    expected_stage=DayStage.VOTE,
                )
            retries += 1

    def _run_hunter_shot(self) -> None:
        """猎人开枪阶段"""
        # 找出应该开枪的猎人
        hunter = self._find_triggered_hunter()
        if hunter is None:
            return
        agent = self.agents.get(hunter.id)
        if agent is None:
            return
        self._agent_decide_and_submit(
            agent,
            "decide_hunter_shot",
            expected_stage=DayStage.JUDGMENT,
        )

    def _find_triggered_hunter(self):
        """找到已死亡且可以开枪的猎人"""
        for p in self.engine.players:  # type: ignore
            if not p.alive and p.role == Role.HUNTER:
                # 被放逐或夜晚死亡
                if (self.engine.vote_exiled == p.id or  # type: ignore
                        p.id in self.engine.night_deaths):  # type: ignore
                    return p
        return None

    # ── Agent 决策与提交 ─────────────────────────────────

    def _agent_decide_and_submit(
        self,
        agent: BaseAgent,
        decide_method: str,
        expected_stage=None,
    ) -> bool:
        """
        为一个 Agent 构建视角、决策、校验、提交。
        返回 True 表示动作已提交（可能不合法但走了 fallback）。
        """
        try:
            # 1. 构建 AgentView
            view = build_agent_view(self.engine, agent.player_id)  # type: ignore
            agent.receive_view(view)

            # 2. 决策
            action: AgentAction = getattr(agent, decide_method)()

            # 3. 校验
            valid, reason = validate_agent_action(self.engine, action)  # type: ignore

            if not valid:
                # 记录 fallback
                fallback = self._make_fallback_action(agent, decide_method)
                result = self.engine.submit_action(**fallback.to_submit_kwargs())  # type: ignore
                return result.success

            # 4. 提交
            result = self.engine.submit_action(**action.to_submit_kwargs())  # type: ignore
            return result.success

        except Exception as e:
            # 兜底 fallback
            fallback = self._make_fallback_action(agent, decide_method)
            try:
                self.engine.submit_action(**fallback.to_submit_kwargs())  # type: ignore
            except Exception:
                pass
            return False

    def _make_fallback_action(
        self, agent: BaseAgent, decide_method: str
    ) -> AgentAction:
        """生成兜底动作"""
        if decide_method == "decide_night_action":
            return AgentAction(
                actor_id=agent.player_id,
                action_type="skip",
            )
        elif decide_method == "decide_vote":
            targets = [
                p for p in self.engine.players  # type: ignore
                if p.alive and p.id != agent.player_id
            ]
            target_id = targets[0].id if targets else None
            return AgentAction(
                actor_id=agent.player_id,
                action_type="vote",
                target_id=target_id,
            )
        elif decide_method == "decide_hunter_shot":
            targets = [
                p for p in self.engine.players  # type: ignore
                if p.alive and p.id != agent.player_id
            ]
            target_id = targets[0].id if targets else None
            return AgentAction(
                actor_id=agent.player_id,
                action_type="hunter_shot",
                target_id=target_id,
            )
        else:
            return AgentAction(
                actor_id=agent.player_id,
                action_type="speak",
            )

    # ── 工具 ────────────────────────────────────────────

    def _get_alive_agents_by_role(self, role: Role) -> List[BaseAgent]:
        """获取指定角色的存活 Agent 列表"""
        result = []
        for p in self.engine.players:  # type: ignore
            if p.alive and p.role == role:
                agent = self.agents.get(p.id)
                if agent:
                    result.append(agent)
        return result

    def _get_alive_agent_by_role(self, role: Role) -> Optional[BaseAgent]:
        agents = self._get_alive_agents_by_role(role)
        return agents[0] if agents else None
