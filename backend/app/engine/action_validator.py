"""
action_validator — Agent 动作合法性校验

在 Agent 返回 AgentAction 后、提交给引擎前，进行合法性校验。
"""

from __future__ import annotations

from typing import Tuple

from ..schemas.agent import AgentAction
from ..schemas.models import (
    GamePhase,
    NightStage,
    DayStage,
    Role,
)
from ..engine.game_engine import WerewolfGameEngine


def validate_agent_action(
    engine: WerewolfGameEngine,
    action: AgentAction,
) -> Tuple[bool, str]:
    """
    校验 AgentAction 是否合法。
    返回 (valid, reason)。
    """
    if engine.phase == GamePhase.ENDED:
        return False, "Game already ended"

    actor = engine._get_player(action.actor_id)  # type: ignore
    if not actor:
        return False, f"Player {action.actor_id} not found"

    # 基础校验
    if engine.phase == GamePhase.NIGHT:
        return _validate_night_action(engine, actor, action)
    elif engine.phase == GamePhase.DAY:
        return _validate_day_action(engine, actor, action)
    return False, f"Unknown phase: {engine.phase}"


def _validate_night_action(engine, actor, action: AgentAction) -> Tuple[bool, str]:
    night_stage = engine.night_stage  # type: ignore

    if night_stage == NightStage.WEREWOLF_KILL:
        if action.action_type != "werewolf_kill":
            return False, f"Expected werewolf_kill, got {action.action_type}"
        if actor.role != Role.WEREWOLF:
            return False, "Only werewolves can kill"
        return _validate_target_alive(engine, action, same_team_ok=True,
                                       forbid_role=Role.WEREWOLF,
                                       forbid_team=None)

    elif night_stage == NightStage.SEER_INVESTIGATE:
        if action.action_type != "seer_investigate":
            return False, f"Expected seer_investigate, got {action.action_type}"
        if actor.role != Role.SEER:
            return False, "Only seer can investigate"
        return _validate_target_alive(engine, action, forbid_self=True)

    elif night_stage == NightStage.WITCH_ACTION:
        if action.action_type != "witch_action":
            return False, f"Expected witch_action, got {action.action_type}"
        if actor.role != Role.WITCH:
            return False, "Only witch can use potions"
        # 女巫 action 的 content 校验留给引擎
        return True, ""

    return False, f"Unknown night stage: {night_stage}"


def _validate_day_action(engine, actor, action: AgentAction) -> Tuple[bool, str]:
    day_stage = engine.day_stage  # type: ignore

    if day_stage == DayStage.SPEAK:
        if action.action_type != "speak":
            return False, "Only speak allowed in speak stage"
        if not actor.alive:
            return False, "Dead players cannot speak"
        return True, ""

    if day_stage == DayStage.VOTE:
        if action.action_type != "vote":
            return False, f"Expected vote, got {action.action_type}"
        if not actor.alive:
            return False, "Dead players cannot vote"
        return _validate_target_alive(engine, action, forbid_self=True)

    if day_stage == DayStage.JUDGMENT:
        if action.action_type == "hunter_shot":
            if actor.role != Role.HUNTER:
                return False, "Only hunter can shoot"
            return _validate_target_alive(engine, action, forbid_self=True)
        return False, f"Action {action.action_type} not allowed in judgment"

    return False, f"Unknown day stage: {day_stage}"


def _validate_target_alive(
    engine,
    action: AgentAction,
    forbid_self: bool = False,
    same_team_ok: bool = True,
    forbid_role=None,
    forbid_team=None,
) -> Tuple[bool, str]:
    """通用目标存活校验"""
    if action.target_id is None:
        return False, "Target is required"

    target = engine._get_player(action.target_id)  # type: ignore
    if not target:
        return False, f"Target {action.target_id} not found"
    if not target.alive:
        return False, "Target is already dead"
    if forbid_self and target.id == action.actor_id:
        return False, "Cannot target self"
    if forbid_role is not None and target.role == forbid_role:
        return False, f"Cannot target {forbid_role.value}"
    if forbid_team is not None and target.team == forbid_team:
        return False, f"Cannot target own team member"
    return True, ""
