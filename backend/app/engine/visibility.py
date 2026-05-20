"""
visibility — 信息隔离层

根据当前引擎状态为指定玩家构建 AgentView。
严格遵循信息隔离规则：非狼人看不到狼人身份，非预言家看不到查验结果等。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..schemas.agent import (
    AgentView,
    InvestigationResult,
    PrivateInfo,
    PublicPlayerInfo,
    SelfPlayerInfo,
)
from ..schemas.models import (
    DayStage,
    GamePhase,
    NightStage,
    Role,
    Team,
)
from ..engine.game_engine import WerewolfGameEngine


def build_agent_view(
    engine: WerewolfGameEngine,
    player_id: int,
) -> AgentView:
    """
    为 player_id 构建 AgentView。
    每次调用都会重新从引擎获取最新状态，保证时效性和隔离性。
    """
    player = engine._get_player(player_id)  # type: ignore
    if player is None:
        raise ValueError(f"Player {player_id} not found")

    # ── self_player ───────────────────────────────────
    self_info = SelfPlayerInfo(
        player_id=player.id,
        name=player.name,
        role=player.role.value,
        alive=player.alive,
    )

    # ── public_players（不含 role）────────────────────
    public_players = [
        PublicPlayerInfo(player_id=p.id, name=p.name, alive=p.alive)
        for p in engine.players  # type: ignore
    ]

    # ── public_events ─────────────────────────────────
    public_events = _build_public_events(engine)

    # ── private_info ──────────────────────────────────
    private_info = _build_private_info(engine, player_id)

    # ── legal_actions ─────────────────────────────────
    legal_actions = _get_legal_actions(engine, player)

    state = engine.get_state()  # type: ignore
    return AgentView(
        game_id=engine.game_id,  # type: ignore
        round=state.round_num,
        phase=state.phase if state.phase else "",
        day_stage=state.day_stage if state.day_stage else None,
        night_stage=state.night_stage if state.night_stage else None,
        self_player=self_info,
        public_players=public_players,
        public_events=public_events,
        private_info=private_info,
        legal_actions=legal_actions,
    )


def _build_public_events(engine: WerewolfGameEngine) -> List[Dict[str, Any]]:
    """从引擎日志中提取公开事件（死亡公告、放逐公告、发言等）"""
    events: List[Dict[str, Any]] = []

    # 从 round_logs 提取公开信息
    for rlog in getattr(engine, "round_logs", []):
        for act in rlog.actions:
            if act.action_type in (
                "announce_death", "vote_result", "speak",
                "night_resolve", "game_over",
            ):
                events.append({
                    "event_type": act.action_type,
                    "actor_id": act.actor_id,
                    "content": act.content or "",
                    "round": rlog.round,
                })

    # 当前轮次未 finalize 的动作也加入
    for act in getattr(engine, "_current_actions", []):
        if act.action_type in ("announce_death", "vote_result", "speak",
                                "night_resolve", "game_over"):
            events.append({
                "event_type": act.action_type,
                "actor_id": act.actor_id,
                "content": act.content or "",
                "round": getattr(engine, "round_num", 0),
            })

    return events


def _build_private_info(engine: WerewolfGameEngine, player_id: int) -> PrivateInfo:
    """根据玩家角色构建私有信息，严格遵守信息隔离"""
    player = engine._get_player(player_id)  # type: ignore
    if player is None:
        return PrivateInfo()

    info = PrivateInfo()
    role = player.role

    if role == Role.WEREWOLF:
        # 狼人知道其他狼人
        info.known_wolves = [
            p.id for p in engine.players  # type: ignore
            if p.role == Role.WEREWOLF and p.id != player_id and p.alive
        ]

    elif role == Role.SEER:
        # 预言家只能看到自己的查验结果（从日志中提取）
        results: List[InvestigationResult] = []
        for rlog in getattr(engine, "round_logs", []):
            for act in rlog.actions:
                if act.actor_id == player_id and act.action_type == "seer_investigate":
                    # 从 content 解析结果
                    # 格式： "查验 XXX: 好人" 或 "查验 XXX: 狼人"
                    if act.content and "查验" in act.content:
                        is_wolf = "狼人" in act.content
                        target_name = ""
                        if ":" in act.content:
                            target_name = act.content.split(":")[0].replace("查验 ", "").strip()
                        target_id = act.target_id or 0
                        results.append(InvestigationResult(
                            target_id=target_id,
                            target_name=target_name,
                            is_werewolf=is_wolf,
                            round=rlog.round,
                        ))
        info.investigation_results = results

    elif role == Role.WITCH:
        # 女巫能看到药水状态
        info.has_antidote = not getattr(engine, "witch_save_used", True)
        info.has_poison = not getattr(engine, "witch_poison_used", True)
        info.antidote_used = getattr(engine, "witch_save_used", False)
        info.poison_used = getattr(engine, "witch_poison_used", False)
        info.tonight_kill_target = getattr(engine, "night_kill_target", None)

    elif role == Role.HUNTER:
        # 猎人能知道自己是否可开枪
        alive = player.alive
        info.can_shoot = not alive  # 已死亡才能开枪

    # 村民没有任何私有信息

    return info


def _get_legal_actions(
    engine: WerewolfGameEngine,
    player,
) -> List[str]:
    """根据当前阶段返回该玩家允许的动作类型"""
    phase = getattr(engine, "phase", None)
    if phase == GamePhase.ENDED:
        return []

    if phase == GamePhase.NIGHT:
        night_stage = getattr(engine, "night_stage", None)
        if night_stage == NightStage.WEREWOLF_KILL:
            return ["werewolf_kill"] if player.role == Role.WEREWOLF else ["skip"]
        elif night_stage == NightStage.SEER_INVESTIGATE:
            return ["seer_investigate"] if player.role == Role.SEER else ["skip"]
        elif night_stage == NightStage.WITCH_ACTION:
            return ["witch_action"] if player.role == Role.WITCH else ["skip"]
        return ["skip"]

    if phase == GamePhase.DAY:
        day_stage = getattr(engine, "day_stage", None)
        actions = []
        if day_stage in (DayStage.SPEAK,):
            actions.append("speak")
        if day_stage in (DayStage.VOTE,):
            actions.append("vote")
        if day_stage == DayStage.JUDGMENT:
            if player.role == Role.HUNTER and not player.alive:
                actions.append("hunter_shot")
            # 如果白天阶段是 JUDGMENT 且玩家还活着，看是否在投票后等待
            if player.alive and getattr(engine, "vote_exiled", None) is not None:
                actions.append("vote")  # 实际这种情况不太会需要，保留安全
        if not actions:
            actions.append("skip")
        return actions

    return []
