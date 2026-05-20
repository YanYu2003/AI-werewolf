"""
WebSocketManager — 管理 WebSocket 连接和广播
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import WebSocket


class WebSocketManager:
    """
    管理所有活跃游戏房间的 WebSocket 连接。
    每个 game_id 对应一个连接集合。
    """

    def __init__(self):
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, game_id: int, ws: WebSocket):
        """接受 WebSocket 连接并加入房间"""
        await ws.accept()
        if game_id not in self._connections:
            self._connections[game_id] = set()
        self._connections[game_id].add(ws)

    def disconnect(self, game_id: int, ws: WebSocket):
        """断开连接并移除"""
        if game_id in self._connections:
            self._connections[game_id].discard(ws)
            if not self._connections[game_id]:
                del self._connections[game_id]

    async def broadcast(self, game_id: int, message: Dict[str, Any]):
        """向游戏房间广播消息"""
        if game_id not in self._connections:
            return
        dead: List[WebSocket] = []
        for ws in self._connections[game_id]:
            try:
                data = json.dumps(message, ensure_ascii=False, default=str)
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[game_id].discard(ws)
        if game_id in self._connections and not self._connections[game_id]:
            del self._connections[game_id]

    async def broadcast_snapshot(self, game_id: int, state_dict: Dict[str, Any]):
        """推送快照给房间内所有连接"""
        await self.broadcast(game_id, {
            "type": "snapshot",
            "game_id": game_id,
            "payload": {"state": state_dict},
            "timestamp": datetime.now().isoformat(),
        })

    async def send_snapshot(self, ws: WebSocket, game_id: int, state_dict: Dict[str, Any]):
        """向指定连接推送快照（仅用于新连接首次推送）"""
        try:
            data = json.dumps({
                "type": "snapshot",
                "game_id": game_id,
                "payload": {"state": state_dict},
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False, default=str)
            await ws.send_text(data)
        except Exception:
            pass

    async def broadcast_event(self, game_id: int, event: Dict[str, Any]):
        """推送事件"""
        await self.broadcast(game_id, {
            "type": "event",
            "game_id": game_id,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        })

    async def broadcast_error(self, game_id: int, message: str):
        """推送错误"""
        await self.broadcast(game_id, {
            "type": "error",
            "game_id": game_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })

    def get_connection_count(self, game_id: int) -> int:
        """获取某个游戏的连接数"""
        return len(self._connections.get(game_id, set()))

    def get_active_games(self) -> List[int]:
        """获取有活跃连接的游戏 ID 列表"""
        return [gid for gid, conns in self._connections.items() if conns]
