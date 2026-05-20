"""
AI 狼人杀 — 游戏服务层

封装 WerewolfGameEngine 的创建、行动提交、状态查询和日志导出。
提供面向外部调用（API、CLI）的统一接口。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..engine.game_engine import WerewolfGameEngine
from ..schemas.models import (
    ActionResult,
    GameLogResponse,
    GameStateResponse,
    Role,
)


class GameService:
    """
    游戏服务：管理游戏实例的生命周期。
    每个游戏实例对应一个 WerewolfGameEngine，由 game_id 索引。
    """

    def __init__(self):
        self._games: Dict[int, WerewolfGameEngine] = {}
        self._next_game_id: int = 1

    # ── 游戏创建 ──────────────────────────────────────────

    def create_game(
        self,
        player_names: List[str],
        custom_roles: Optional[List[Role]] = None,
    ) -> Dict[str, Any]:
        """
        创建新游戏。

        参数:
            player_names: 玩家名称列表
            custom_roles: 可选的角色列表（与玩家顺序对应）

        返回:
            {
                "game_id": int,
                "players": [{"id": int, "name": str, "role": str, "team": str}, ...],
                "status": str
            }
        """
        if len(player_names) < 2:
            return {"error": "至少需要 2 名玩家"}

        game_id = self._next_game_id
        self._next_game_id += 1

        engine = WerewolfGameEngine(
            game_id=game_id,
            player_names=player_names,
            custom_roles=custom_roles,
        )

        self._games[game_id] = engine

        players_info = [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role.value,
                "team": p.team.value,
                "alive": p.alive,
            }
            for p in engine.players
        ]

        return {
            "game_id": game_id,
            "players": players_info,
            "status": "created",
        }

    # ── 行动提交 ──────────────────────────────────────────

    def submit_action(
        self,
        game_id: int,
        action_type: str,
        actor_id: int,
        target_id: Optional[int] = None,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        提交行动。

        返回:
            ActionResult 的 dict 表示
        """
        engine = self._games.get(game_id)
        if not engine:
            return {"success": False, "message": f"游戏 {game_id} 不存在"}

        result = engine.submit_action(
            action_type=action_type,
            actor_id=actor_id,
            target_id=target_id,
            content=content,
        )
        return result.model_dump()

    # ── 状态查询 ──────────────────────────────────────────

    def get_state(self, game_id: int) -> Dict[str, Any]:
        """获取游戏当前状态"""
        engine = self._games.get(game_id)
        if not engine:
            return {"error": f"游戏 {game_id} 不存在"}
        return engine.get_state().model_dump()

    def get_player_view(self, game_id: int, player_id: int) -> Dict[str, Any]:
        """获取玩家视角信息"""
        engine = self._games.get(game_id)
        if not engine:
            return {"error": f"游戏 {game_id} 不存在"}
        return engine.get_player_view(player_id)

    def get_log(self, game_id: int) -> Dict[str, Any]:
        """获取完整游戏日志"""
        engine = self._games.get(game_id)
        if not engine:
            return {"error": f"游戏 {game_id} 不存在"}
        response = engine.get_log()
        return response.model_dump()

    # ── 工具 ──────────────────────────────────────────────

    def list_games(self) -> List[Dict[str, Any]]:
        """列出所有活跃游戏"""
        result = []
        for gid, engine in self._games.items():
            state = engine.get_state()
            result.append({
                "game_id": gid,
                "phase": state.phase.value if state.phase else None,
                "round_num": state.round_num,
                "alive_count": len(state.alive_players),
                "winner": state.winner.value if state.winner else None,
            })
        return result
