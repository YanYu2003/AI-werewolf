"""
Phase 3 — API 请求/响应模型
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── 请求模型 ──────────────────────────────────────────

class HumanPlayerConfig(BaseModel):
    """创建游戏时指定的人类玩家"""
    player_id: Optional[int] = None  # 前端不关心 ID 时留空
    name: str


class GameConfig(BaseModel):
    """游戏配置"""
    enable_human: bool = False
    auto_start: bool = True
    seed: Optional[int] = None


class CreateGameRequest(BaseModel):
    """POST /api/games 请求体"""
    player_count: int = 8
    player_names: Optional[List[str]] = None
    human_players: List[HumanPlayerConfig] = []
    config: GameConfig = GameConfig()


class AutoRunRequest(BaseModel):
    """POST /api/games/{id}/auto-run 请求体"""
    max_steps: int = 200


class HumanActionRequest(BaseModel):
    """POST /api/games/{id}/players/{pid}/actions 请求体"""
    action_type: str
    target_id: Optional[int] = None
    content: Optional[str] = None
    metadata: dict = {}


# ── 响应模型 ──────────────────────────────────────────

class PlayerPublicInfo(BaseModel):
    """公开玩家信息（无隐藏身份）"""
    player_id: int
    name: str
    type: str  # "human" | "ai"
    alive: bool
    role: Optional[str] = None       # 仅游戏结束后公开
    revealed_role: Optional[str] = None  # 因规则公开的身份


class GameListItem(BaseModel):
    """游戏列表中的一项"""
    game_id: int
    status: str                      # "created" / "running" / "finished"
    current_round: int
    current_phase: str
    winner_team: Optional[str] = None
    created_at: str
    updated_at: str


class CreateGameResponse(BaseModel):
    """POST /api/games 响应"""
    game_id: int
    status: str
    players: List[PlayerPublicInfo]
    current_round: int
    current_phase: str


class GameListResponse(BaseModel):
    """GET /api/games 响应"""
    games: List[GameListItem]


class PublicGameState(BaseModel):
    """GET /api/games/{id}/state 响应（公开视图）"""
    game_id: int
    status: str
    current_round: int
    current_phase: str
    day_stage: Optional[str] = None
    night_stage: Optional[str] = None
    winner_team: Optional[str] = None
    players: List[PlayerPublicInfo]
    public_events: List[Dict[str, Any]] = []
    available_actions: List[str] = []


class StepResponse(BaseModel):
    """POST /api/games/{id}/step 响应"""
    game_id: int
    status: str
    applied_events: List[Dict[str, Any]] = []
    current_round: int
    current_phase: str
    waiting_for_human: bool = False
    pending_player_id: Optional[int] = None
    legal_actions: List[str] = []


class AutoRunResponse(BaseModel):
    """POST /api/games/{id}/auto-run 响应"""
    game_id: int
    status: str
    winner_team: Optional[str] = None
    steps: int = 0
    stopped_reason: str = ""


class HumanActionResponse(BaseModel):
    """POST /api/games/{id}/players/{pid}/actions 响应"""
    accepted: bool
    game_id: int
    player_id: int
    action: Optional[Dict[str, Any]] = None
    next_state: Optional[PublicGameState] = None
    reason: str = ""


class LogEntry(BaseModel):
    """安全日志条目"""
    round: int
    actions: List[Dict[str, Any]]


class GameLogResponse(BaseModel):
    """GET /api/games/{id}/logs 响应"""
    game_id: int
    logs: List[LogEntry]


class ReplayEvent(BaseModel):
    """回放事件"""
    index: int
    round: int
    phase: str
    event_type: str
    public_payload: Dict[str, Any] = {}
    timestamp: str


class FinalRoleInfo(BaseModel):
    """最终角色公开信息"""
    player_id: int
    name: str
    role: str


class ReplayResponse(BaseModel):
    """GET /api/games/{id}/replay 响应"""
    game_id: int
    status: str
    winner_team: Optional[str] = None
    events: List[ReplayEvent] = []
    final_roles: List[FinalRoleInfo] = []
