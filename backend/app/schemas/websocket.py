"""
Phase 3 — WebSocket 消息模型
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WsSnapshotPayload(BaseModel):
    """连接时推送的完整快照"""
    state: Dict[str, Any]  # PublicGameState dict


class WsSnapshot(BaseModel):
    """WebSocket 快照消息"""
    type: str = "snapshot"
    game_id: int
    payload: WsSnapshotPayload
    timestamp: str


class WsEvent(BaseModel):
    """WebSocket 事件消息"""
    type: str = "event"
    game_id: int
    event: Dict[str, Any]
    timestamp: str


class WsError(BaseModel):
    """WebSocket 错误消息"""
    type: str = "error"
    game_id: int
    message: str
    timestamp: str
