"""
GameRunner — 增强的游戏运行器

支持 step-by-step 执行、人机混战、WebSocket 事件推送。
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from ..agents.factory import create_agents_for_game
from ..engine.action_validator import validate_agent_action
from ..engine.game_engine import WerewolfGameEngine
from ..engine.visibility import build_agent_view
from ..schemas.agent import AgentAction
from ..schemas.api import PublicGameState
from ..schemas.models import (
    DayStage,
    GamePhase,
    NightStage,
    Role,
)
from .public_state_service import build_public_state
from .websocket_manager import WebSocketManager


class GameRunner:
    """
    管理一局游戏的完整生命周期，支持 step 式推进和人机混战。

    每个 GameRunner 对应一局游戏，持有：
    - engine: WerewolfGameEngine
    - agents: AI Agent 字典
    - human_player_ids: 人类玩家 ID 集合
    - ws_manager: WebSocket 管理器引用
    """

    def __init__(
        self,
        engine: WerewolfGameEngine,
        human_player_ids: Optional[List[int]] = None,
        ws_manager: Optional[WebSocketManager] = None,
    ):
        self.engine = engine
        self.human_player_ids: Set[int] = set(human_player_ids or [])
        self.ws_manager = ws_manager
        self.status: str = "created"
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self._pending_human: Optional[int] = None  # 等待 human action 的 player_id

        # 为 AI 玩家创建 Agent
        self.agents: Dict[int, Any] = {}
        for p in engine.players:
            if p.id not in self.human_player_ids:
                from ..agents.factory import create_agent
                self.agents[p.id] = create_agent(p.id, p.role, p.name)

    # ── 状态查询 ───────────────────────────────────

    def get_public_state(self) -> PublicGameState:
        """获取当前公开状态"""
        status = self.status
        if self.engine.phase == GamePhase.ENDED:
            status = "finished"
        elif self._pending_human is not None:
            status = "waiting_human"
        else:
            status = "running"
        return build_public_state(
            self.engine,
            list(self.human_player_ids),
            status=status,
        )

    def get_player_view(self, player_id: int) -> Dict[str, Any]:
        """获取某个玩家的私有视角（仅限 human player 查询自己的视角）"""
        # TODO: auth required for production
        if player_id not in self.human_player_ids:
            return {"error": "Forbidden: only human players can query private view via API"}
        player = self.engine._get_player(player_id)
        if not player:
            return {"error": "Player not found"}
        view = build_agent_view(self.engine, player_id)
        d = view.model_dump()
        d["legal_actions"] = self._get_human_legal_actions(player_id)
        return d

    def _get_human_legal_actions(self, player_id: int) -> List[str]:
        """返回人类玩家当前可用的动作"""
        if self.engine.phase == GamePhase.ENDED:
            return []
        player = self.engine._get_player(player_id)
        if not player or not player.alive:
            return []
        if self.engine.phase == GamePhase.NIGHT:
            night_stage = self.engine.night_stage
            if night_stage == NightStage.WEREWOLF_KILL and player.role == Role.WEREWOLF:
                return ["werewolf_kill"]
            if night_stage == NightStage.SEER_INVESTIGATE and player.role == Role.SEER:
                return ["seer_investigate"]
            if night_stage == NightStage.WITCH_ACTION and player.role == Role.WITCH:
                return ["witch_action"]
            return []
        if self.engine.phase == GamePhase.DAY:
            day_stage = self.engine.day_stage
            actions = []
            if day_stage == DayStage.SPEAK:
                actions.append("speak")
            if day_stage == DayStage.VOTE:
                actions.append("vote")
            if day_stage == DayStage.JUDGMENT and player.role == Role.HUNTER and not player.alive:
                actions.append("hunter_shot")
            return actions
        return []

    # ── Step 式推进 ────────────────────────────────

    async def step(self) -> Dict[str, Any]:
        """推进一步游戏，返回应用的事件列表"""
        events: List[Dict[str, Any]] = []
        self.updated_at = datetime.now().isoformat()

        if self.engine.phase == GamePhase.ENDED:
            self.status = "finished"
            self._pending_human = None
            return {"events": events, "waiting_for_human": False}

        # 检查是否轮到 human 行动
        if self._pending_human is not None:
            return {"events": events, "waiting_for_human": True}

        # 检查当前阶段是否应等待 human
        human_pending = self._check_human_pending()
        if human_pending is not None:
            self._pending_human = human_pending
            return {"events": events, "waiting_for_human": True}

        # 执行 AI 动作
        action_event = await self._execute_ai_action()
        if action_event:
            events.extend(action_event)

        # 如果游戏结束，更新状态
        if self.engine.phase == GamePhase.ENDED:
            self.status = "finished"

        # 再次检查 human pending（推进后可能轮到 human）
        if not self.engine.phase == GamePhase.ENDED:
            human_pending = self._check_human_pending()
            if human_pending is not None:
                self._pending_human = human_pending

        # WebSocket 推送
        if self.ws_manager and events:
            for ev in events:
                await self.ws_manager.broadcast_event(self.engine.game_id, ev)

        return {
            "events": events,
            "waiting_for_human": self._pending_human is not None,
        }

    def _check_human_pending(self) -> Optional[int]:
        """检查当前阶段是否有 human 玩家需要行动"""
        if self.engine.phase == GamePhase.ENDED:
            return None

        # 夜晚阶段
        if self.engine.phase == GamePhase.NIGHT:
            night_stage = self.engine.night_stage
            if night_stage == NightStage.WEREWOLF_KILL:
                for p in self.engine.players:
                    if p.alive and p.role == Role.WEREWOLF and p.id in self.human_player_ids:
                        if p.id not in getattr(self.engine, "werewolf_kills", {}):
                            return p.id
            elif night_stage == NightStage.SEER_INVESTIGATE:
                for p in self.engine.players:
                    if p.alive and p.role == Role.SEER and p.id in self.human_player_ids:
                        return p.id
            elif night_stage == NightStage.WITCH_ACTION:
                for p in self.engine.players:
                    if p.alive and p.role == Role.WITCH and p.id in self.human_player_ids:
                        return p.id
            return None

        # 白天阶段
        if self.engine.phase == GamePhase.DAY:
            day_stage = self.engine.day_stage
            if day_stage == DayStage.SPEAK:
                for p in self.engine.players:
                    if p.alive and p.id in self.human_player_ids and p.id not in getattr(self.engine, "spoken_players", set()):
                        return p.id
            elif day_stage == DayStage.VOTE:
                for p in self.engine.players:
                    if p.alive and p.id in self.human_player_ids and p.id not in getattr(self.engine, "day_votes", {}):
                        return p.id
            elif day_stage == DayStage.JUDGMENT:
                for p in self.engine.players:
                    if not p.alive and p.role == Role.HUNTER and p.id in self.human_player_ids:
                        return p.id
            return None
        return None

    # ── Human Action ───────────────────────────────

    async def submit_human_action(
        self, player_id: int, action_type: str,
        target_id: Optional[int] = None, content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提交人类玩家动作"""
        if self._pending_human != player_id:
            return {"accepted": False, "reason": f"Not your turn (waiting for player {self._pending_human})"}

        if self.engine.phase == GamePhase.ENDED:
            self._pending_human = None
            return {"accepted": False, "reason": "Game already ended"}

        # 构建 AgentAction 并校验
        action = AgentAction(
            actor_id=player_id,
            action_type=action_type,
            target_id=target_id,
            content=content,
        )
        valid, reason = validate_agent_action(self.engine, action)
        if not valid:
            return {"accepted": False, "reason": reason}

        # 提交到引擎
        result = self.engine.submit_action(
            action_type=action_type,
            actor_id=player_id,
            target_id=target_id,
            content=content,
        )

        if not result.success:
            return {"accepted": False, "reason": result.message}

        self._pending_human = None
        self.updated_at = datetime.now().isoformat()

        # 检查是否又轮到另一个 human
        next_pending = self._check_human_pending()
        if next_pending is not None:
            self._pending_human = next_pending

        if self.engine.phase == GamePhase.ENDED:
            self.status = "finished"

        # WebSocket 推送
        if self.ws_manager:
            event = {
                "event_type": f"human_{action_type}",
                "player_id": player_id,
                "action_type": action_type,
                "target_id": target_id,
            }
            await self.ws_manager.broadcast_event(self.engine.game_id, event)

        return {
            "accepted": True,
            "reason": "",
            "action": action.model_dump(),
        }

    # ── Auto Run ──────────────────────────────────

    async def auto_run(self, max_steps: int = 200) -> Dict[str, Any]:
        """自动跑完整局或直到等待 human"""
        steps = 0
        stopped_reason = ""

        while steps < max_steps:
            if self.engine.phase == GamePhase.ENDED:
                stopped_reason = "game_over"
                break

            step_result = await self.step()
            steps += 1

            if step_result.get("waiting_for_human"):
                stopped_reason = "waiting_for_human"
                break

        if not stopped_reason:
            stopped_reason = "max_steps_reached"

        self.status = "finished" if self.engine.phase == GamePhase.ENDED else self.status
        state = self.engine.get_state()
        return {
            "status": self.status,
            "winner_team": str(state.winner) if state.winner else None,
            "steps": steps,
            "stopped_reason": stopped_reason,
        }

    # ── AI 执行 ──────────────────────────────────

    async def _execute_ai_action(self) -> List[Dict[str, Any]]:
        """执行一个 AI 动作，返回事件列表"""
        events: List[Dict[str, Any]] = []

        # 夜晚 — 狼人
        if (self.engine.phase == GamePhase.NIGHT
                and self.engine.night_stage == NightStage.WEREWOLF_KILL):
            wolves = [p for p in self.engine.players if p.alive and p.role == Role.WEREWOLF]
            ai_wolves = [w for w in wolves if w.id not in self.human_player_ids]
            # 检查是否有 AI 狼人未投票
            for wolf in ai_wolves:
                if wolf.id not in getattr(self.engine, "werewolf_kills", {}):
                    agent = self.agents.get(wolf.id)
                    if agent:
                        self._agent_act(agent, "decide_night_action", events)
            return events

        # 夜晚 — 预言家
        if (self.engine.phase == GamePhase.NIGHT
                and self.engine.night_stage == NightStage.SEER_INVESTIGATE):
            seer = next((p for p in self.engine.players if p.alive and p.role == Role.SEER and p.id not in self.human_player_ids), None)
            if seer:
                agent = self.agents.get(seer.id)
                if agent:
                    self._agent_act(agent, "decide_night_action", events)
            return events

        # 夜晚 — 女巫
        if (self.engine.phase == GamePhase.NIGHT
                and self.engine.night_stage == NightStage.WITCH_ACTION):
            witch = next((p for p in self.engine.players if p.alive and p.role == Role.WITCH and p.id not in self.human_player_ids), None)
            if witch:
                agent = self.agents.get(witch.id)
                if agent:
                    self._agent_act(agent, "decide_night_action", events)
            return events

        # 白天 — 发言
        if (self.engine.phase == GamePhase.DAY
                and self.engine.day_stage == DayStage.SPEAK):
            alive = [p for p in self.engine.players if p.alive]
            for p in alive:
                if p.id not in self.human_player_ids and p.id not in getattr(self.engine, "spoken_players", set()):
                    agent = self.agents.get(p.id)
                    if agent:
                        self._agent_act(agent, "speak", events)
                    return events
            return events

        # 白天 — 投票
        if (self.engine.phase == GamePhase.DAY
                and self.engine.day_stage == DayStage.VOTE):
            alive = [p for p in self.engine.players if p.alive]
            for p in alive:
                if p.id not in self.human_player_ids and p.id not in getattr(self.engine, "day_votes", {}):
                    agent = self.agents.get(p.id)
                    if agent:
                        self._agent_act(agent, "decide_vote", events)
                    return events
            return events

        # 白天 — 猎人开枪
        if (self.engine.phase == GamePhase.DAY
                and self.engine.day_stage == DayStage.JUDGMENT):
            hunter = next((p for p in self.engine.players if not p.alive and p.role == Role.HUNTER and p.id not in self.human_player_ids), None)
            if hunter:
                agent = self.agents.get(hunter.id)
                if agent:
                    self._agent_act(agent, "decide_hunter_shot", events)
                return events
            return events

        return events

    def _agent_act(self, agent, method: str, events: List[Dict[str, Any]]):
        """让 Agent 执行一个动作"""
        try:
            view = build_agent_view(self.engine, agent.player_id)
            agent.receive_view(view)
            action: AgentAction = getattr(agent, method)()

            valid, reason = validate_agent_action(self.engine, action)
            if not valid:
                return

            self.engine.submit_action(**action.to_submit_kwargs())
            events.append({
                "event_type": f"ai_{action.action_type}",
                "actor_id": action.actor_id,
                "action_type": action.action_type,
                "target_id": action.target_id,
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Agent action failed (player_id=%s, method=%s): %s",
                            agent.player_id if hasattr(agent, 'player_id') else '?', method, str(e))
            # 记录系统日志
            self.engine._add_action("agent_error", 0, target_id=None, content=f"Agent {method} failed: {type(e).__name__}")

    # ── 日志 / 回放 ─────────────────────────────────

    def get_logs(self) -> Dict[str, Any]:
        """获取完整日志"""
        log = self.engine.get_log()
        return log.model_dump()

    def get_replay(self) -> Dict[str, Any]:
        """获取回放数据"""
        log = self.engine.get_log()
        log_data = log.model_dump()
        events: List[Dict[str, Any]] = []
        idx = 0

        for rlog in log_data.get("logs", []):
            for act in rlog.get("actions", []):
                action_type = act.get("action_type", "")
                # 跳过 system 内部动作，只保留可见事件
                if action_type in (
                    "announce_death", "vote_result", "speak",
                    "game_over", "night_resolve",
                    "werewolf_kill", "seer_investigate",
                    "vote", "hunter_shot", "hunter_triggered",
                ):
                    # 安全：不暴露隐藏角色
                    is_ended = self.engine.phase == GamePhase.ENDED
                    safe_role = act.get("role") if is_ended else "hidden"
                    events.append({
                        "index": idx,
                        "round": rlog.get("round", 0),
                        "phase": "night" if action_type in (
                            "werewolf_kill", "seer_investigate",
                            "night_resolve",
                        ) else "day",
                        "event_type": action_type,
                        "public_payload": {
                            "actor_id": act.get("actor_id"),
                            "role": safe_role,
                            "content": act.get("content", ""),
                        },
                        "timestamp": act.get("timestamp", ""),
                    })
                    idx += 1

        is_ended = self.engine.phase == GamePhase.ENDED
        winner = None
        if is_ended:
            s = self.engine.get_state()
            winner = str(s.winner) if s.winner else None

        final_roles = []
        if is_ended:
            for p in self.engine.players:
                final_roles.append({
                    "player_id": p.id,
                    "name": p.name,
                    "role": p.role.value,
                })

        return {
            "game_id": self.engine.game_id,
            "status": "finished" if is_ended else self.status,
            "winner_team": winner,
            "events": events,
            "final_roles": final_roles,
        }
