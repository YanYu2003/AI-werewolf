"""
PublicStateService — 安全公开状态生成

确保任何 API / WebSocket 响应不泄露隐藏身份。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..schemas.api import PlayerPublicInfo, PublicGameState
from ..schemas.models import GamePhase, Team
from ..engine.game_engine import WerewolfGameEngine


def build_public_state(
    engine: WerewolfGameEngine,
    human_player_ids: List[int],
    status: str = "running",
) -> PublicGameState:
    """
    从引擎状态生成安全的公开状态。
    游戏未结束前，role 字段全部为 None。
    游戏结束后，role 公开。
    """
    state = engine.get_state()
    is_ended = state.phase == GamePhase.ENDED
    winner = state.winner

    players: List[PlayerPublicInfo] = []
    for p in engine.players:
        role_val = None
        if is_ended:
            role_val = p.role.value

        # 因规则公开的身份：猎人被放逐/死亡时开枪会上报
        revealed = None

        players.append(PlayerPublicInfo(
            player_id=p.id,
            name=p.name,
            type="human" if p.id in human_player_ids else "ai",
            alive=p.alive,
            role=role_val,
            revealed_role=revealed,
        ))

    # 构建公开事件列表（从引擎日志提取安全的公开事件）
    public_events = _build_public_events(engine)

    # 可用的公开动作（非 human 视角不需要 action list）
    available_actions = _get_public_actions(engine)

    phase_str = str(state.phase) if state.phase else ""
    day_stage = str(state.day_stage) if state.day_stage else None
    night_stage = str(state.night_stage) if state.night_stage else None

    return PublicGameState(
        game_id=engine.game_id,
        status=status,
        current_round=state.round_num,
        current_phase=phase_str,
        day_stage=day_stage,
        night_stage=night_stage,
        winner_team=str(winner) if (is_ended and winner) else None,
        players=players,
        public_events=public_events,
        available_actions=available_actions,
    )


def _build_public_events(engine) -> List[Dict[str, Any]]:
    """从日志提取安全的公开事件（不含隐藏身份）"""
    events: List[Dict[str, Any]] = []
    all_logs = list(getattr(engine, "round_logs", []))
    if getattr(engine, "_current_actions", []):
        from ..schemas.models import RoundLog
        all_logs.append(RoundLog(
            round=getattr(engine, "round_num", 0),
            actions=list(getattr(engine, "_current_actions", [])),
        ))

    safe_types = {
        "announce_death", "vote_result", "speak",
        "night_resolve", "game_over", "werewolf_kill_resolved",
    }

    for rlog in all_logs:
        for act in rlog.actions:
            if act.action_type in safe_types:
                # 安全：不暴露真实角色（游戏结束前 role 为 None）
                events.append({
                    "event_type": act.action_type,
                    "actor_id": act.actor_id,
                    "role": None,
                    "content": act.content or "",
                    "round": rlog.round,
                    "timestamp": act.timestamp,
                })
    return events


def _get_public_actions(engine) -> List[str]:
    """返回当前阶段可执行的动作类型（公开视角）"""
    phase = getattr(engine, "phase", None)
    if not phase or phase == GamePhase.ENDED:
        return []
    if phase == GamePhase.NIGHT:
        return []
    if phase == GamePhase.DAY:
        day_stage = getattr(engine, "day_stage", None)
        if day_stage:
            from ..schemas.models import DayStage
            if day_stage == DayStage.SPEAK:
                return ["speak"]
            if day_stage == DayStage.VOTE:
                return ["vote"]
            if day_stage == DayStage.JUDGMENT:
                return ["hunter_shot"]
    return []
