"""
FastAPI 路由 — 游戏 REST API
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ..engine.game_engine import WerewolfGameEngine
from ..schemas.api import (
    AutoRunRequest,
    AutoRunResponse,
    CreateGameRequest,
    CreateGameResponse,
    GameListResponse,
    GameListItem,
    GameLogResponse,
    HumanActionRequest,
    HumanActionResponse,
    LogEntry,
    PlayerPublicInfo,
    PublicGameState,
    ReplayEvent,
    FinalRoleInfo,
    ReplayResponse,
    StepResponse,
)
from ..schemas.models import Team, Role
from ..services.game_runner import GameRunner
from ..services.websocket_manager import WebSocketManager

# 全局存储
_game_runners: Dict[int, GameRunner] = {}
_next_game_id: int = 1
_ws_manager: WebSocketManager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    return _ws_manager


def get_runners() -> Dict[int, GameRunner]:
    return _game_runners


router = APIRouter(prefix="/api")


def _generate_player_names(count: int, human_players: list) -> List[str]:
    """生成玩家名称"""
    default_names = [
        "Alice", "Bob", "Charlie", "Diana", "Eve",
        "Frank", "Grace", "Henry", "Ivy", "Jack",
        "Kate", "Leo",
    ]
    names = []
    next_idx = 0
    # 确保 human 玩家的名称占位
    for hp in human_players:
        names.append(hp.name)
        next_idx += 1
    while len(names) < count:
        if next_idx < len(default_names):
            names.append(default_names[next_idx])
            next_idx += 1
        else:
            names.append(f"Player{len(names)+1}")
    return names[:count]


# ── 1. 创建游戏 ──────────────────────────────────

@router.post("/games", response_model=CreateGameResponse)
async def create_game(req: CreateGameRequest):
    global _next_game_id

    player_count = req.player_count
    if player_count < 2 or player_count > 12:
        raise HTTPException(400, "Player count must be 2-12")

    game_id = _next_game_id
    _next_game_id += 1

    # 生成玩家名称
    player_names = _generate_player_names(player_count, req.human_players)

    # 创建引擎
    engine = WerewolfGameEngine(game_id, player_names)

    # 确定 human player IDs
    human_ids = list(range(1, len(req.human_players) + 1))

    # 创建 Runner
    runner = GameRunner(
        engine=engine,
        human_player_ids=human_ids,
        ws_manager=_ws_manager,
    )
    _game_runners[game_id] = runner

    # 自动开始
    if req.config.auto_start:
        runner.status = "running"

    # 初始状态
    players_info = []
    for p in engine.players:
        players_info.append(PlayerPublicInfo(
            player_id=p.id,
            name=p.name,
            type="human" if p.id in human_ids else "ai",
            alive=p.alive,
            role=None,  # 创建时不公开角色
        ))

    return CreateGameResponse(
        game_id=game_id,
        status=runner.status,
        players=players_info,
        current_round=engine.round_num,
        current_phase="created",
    )


# ── 2. 查询游戏列表 ──────────────────────────────

@router.get("/games", response_model=GameListResponse)
async def list_games():
    games = []
    now = datetime.now().isoformat()
    for gid, runner in _game_runners.items():
        state = runner.get_public_state()
        games.append(GameListItem(
            game_id=gid,
            status=runner.status,
            current_round=state.current_round,
            current_phase=state.current_phase,
            winner_team=state.winner_team,
            created_at=runner.created_at,
            updated_at=runner.updated_at,
        ))
    return GameListResponse(games=games)


# ── 3. 查询公开游戏状态 ──────────────────────────

@router.get("/games/{game_id}/state", response_model=PublicGameState)
async def get_game_state(game_id: int):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")
    return runner.get_public_state()


# ── 4. 查询人类玩家私有视角 ─────────────────────

@router.get("/games/{game_id}/players/{player_id}/view")
async def get_player_view(game_id: int, player_id: int):
    """
    TODO: auth required for production
    返回该 player_id 合法可见的 AgentView。
    仅 human player 可以查询自己的私有视角。
    """
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")
    result = runner.get_player_view(player_id)
    if "error" in result:
        err = result["error"]
        if "Forbidden" in err:
            raise HTTPException(403, err)
        if "not found" in err.lower():
            raise HTTPException(404, err)
        raise HTTPException(400, err)
    return result


# ── 5. 推进 AI 自动对局一步 ─────────────────────

@router.post("/games/{game_id}/step", response_model=StepResponse)
async def step_game(game_id: int):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")

    result = await runner.step()
    state = runner.get_public_state()

    return StepResponse(
        game_id=game_id,
        status=state.status,
        applied_events=result.get("events", []),
        current_round=state.current_round,
        current_phase=state.current_phase,
        waiting_for_human=result.get("waiting_for_human", False),
        pending_player_id=runner._pending_human,
        legal_actions=(
            runner._get_human_legal_actions(runner._pending_human)
            if runner._pending_human else []
        ),
    )


# ── 6. 自动跑完整局 ─────────────────────────────

@router.post("/games/{game_id}/auto-run", response_model=AutoRunResponse)
async def auto_run_game(game_id: int, req: AutoRunRequest = AutoRunRequest()):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")

    result = await runner.auto_run(max_steps=req.max_steps)
    return AutoRunResponse(
        game_id=game_id,
        status=result["status"],
        winner_team=result.get("winner_team"),
        steps=result.get("steps", 0),
        stopped_reason=result.get("stopped_reason", ""),
    )


# ── 7. 提交人类玩家动作 ─────────────────────────

@router.post("/games/{game_id}/players/{player_id}/actions", response_model=HumanActionResponse)
async def submit_human_action(game_id: int, player_id: int, req: HumanActionRequest):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")

    result = await runner.submit_human_action(
        player_id=player_id,
        action_type=req.action_type,
        target_id=req.target_id,
        content=req.content,
    )

    next_state = None
    if result.get("accepted"):
        try:
            next_state = runner.get_public_state()
        except Exception:
            pass

    return HumanActionResponse(
        accepted=result.get("accepted", False),
        game_id=game_id,
        player_id=player_id,
        action=result.get("action"),
        next_state=next_state,
        reason=result.get("reason", ""),
    )


# ── 8. 查询日志 ──────────────────────────────────

@router.get("/games/{game_id}/logs", response_model=GameLogResponse)
async def get_game_logs(game_id: int):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")
    log_data = runner.get_logs()
    logs = []
    for entry in log_data.get("logs", []):
        logs.append(LogEntry(
            round=entry.get("round", 0),
            actions=entry.get("actions", []),
        ))
    return GameLogResponse(game_id=game_id, logs=logs)


# ── 9. 查询回放 ──────────────────────────────────

@router.get("/games/{game_id}/replay", response_model=ReplayResponse)
async def get_game_replay(game_id: int):
    runner = _game_runners.get(game_id)
    if not runner:
        raise HTTPException(404, f"Game {game_id} not found")
    replay = runner.get_replay()
    events = [ReplayEvent(**e) for e in replay.get("events", [])]
    final_roles = [FinalRoleInfo(**r) for r in replay.get("final_roles", [])]
    return ReplayResponse(
        game_id=game_id,
        status=replay.get("status", "unknown"),
        winner_team=replay.get("winner_team"),
        events=events,
        final_roles=final_roles,
    )
