"""
FastAPI WebSocket 端点 — /ws/games/{game_id}
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .routes_games import get_ws_manager, get_runners

ws_router = APIRouter()


@ws_router.websocket("/ws/games/{game_id}")
async def game_websocket(ws: WebSocket, game_id: int):
    ws_manager = get_ws_manager()
    runners = get_runners()
    runner = runners.get(game_id)

    if runner is None:
        await ws.accept()
        import json, datetime
        await ws.send_text(json.dumps({
            "type": "error",
            "game_id": game_id,
            "message": "game not found",
            "timestamp": datetime.datetime.now().isoformat(),
        }))
        await ws.close()
        return

    await ws_manager.connect(game_id, ws)

    try:
        # 推送初始快照
        state = runner.get_public_state()
        await ws_manager.broadcast_snapshot(game_id, state.model_dump())

        # 保持连接，等待后续事件推送
        while True:
            data = await ws.receive_text()
            # 目前不处理客户端消息，仅保持连接
            pass

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(game_id, ws)
