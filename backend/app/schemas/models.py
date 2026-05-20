"""
AI 狼人杀 — 数据模型定义
角色枚举、游戏阶段枚举、Pydantic 数据模型
"""

from __future__ import annotations

import random
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 枚举 ────────────────────────────────────────────────────────

class Role(str, Enum):
    """狼人杀角色"""
    WEREWOLF = "werewolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    VILLAGER = "villager"

    def display_name(self) -> str:
        names = {
            "werewolf": "狼人",
            "seer": "预言家",
            "witch": "女巫",
            "hunter": "猎人",
            "villager": "村民",
        }
        return names[self.value]


class Team(str, Enum):
    """阵营"""
    WOLVES = "wolves"
    VILLAGERS = "villagers"


class GamePhase(str, Enum):
    """游戏主阶段"""
    NIGHT = "night"
    DAY = "day"
    ENDED = "ended"


class NightStage(str, Enum):
    """夜晚子阶段"""
    WEREWOLF_KILL = "werewolf_kill"
    SEER_INVESTIGATE = "seer_investigate"
    WITCH_ACTION = "witch_action"


class DayStage(str, Enum):
    """白天子阶段"""
    ANNOUNCE_DEATH = "announce_death"
    SPEAK = "speak"
    VOTE = "vote"
    JUDGMENT = "judgment"


# ── 玩家 / 游戏核心模型 ─────────────────────────────────────

class Player(BaseModel):
    """玩家对象"""
    id: int
    name: str
    role: Role
    team: Team
    alive: bool = True
    is_poisoned: bool = False       # 被女巫毒杀标记
    is_saved: bool = False           # 被女巫解药救活标记（仅当夜有效）

    class Config:
        frozen = False


class ActionLog(BaseModel):
    """单条动作日志"""
    actor_id: int
    role: str
    action_type: str
    target_id: Optional[int] = None
    content: Optional[str] = None
    timestamp: str


class RoundLog(BaseModel):
    """一轮（一晚+一天）的动作日志"""
    round: int
    actions: List[ActionLog] = []


# ── API / 响应模型 ──────────────────────────────────────────

class GameStateResponse(BaseModel):
    """当前游戏状态（公共信息）"""
    game_id: int
    phase: GamePhase
    night_stage: Optional[NightStage] = None
    day_stage: Optional[DayStage] = None
    round_num: int
    alive_players: List[Player]
    wolves_alive: int = 0
    villagers_alive: int = 0
    winner: Optional[Team] = None

    class Config:
        use_enum_values = True


class ActionResult(BaseModel):
    """提交行动后的返回"""
    success: bool
    message: str = ""
    phase_changed: bool = False
    new_phase: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class GameLogResponse(BaseModel):
    """完整游戏日志"""
    game_id: int
    rounds: int
    winner_team: Optional[str] = None
    logs: List[RoundLog] = []


# ── 默认配置 ────────────────────────────────────────────────

DEFAULT_ROLES_8P = [
    Role.WEREWOLF, Role.WEREWOLF,
    Role.SEER,
    Role.WITCH,
    Role.HUNTER,
    Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
]

DEFAULT_ROLES_6P = [
    Role.WEREWOLF, Role.WEREWOLF,
    Role.SEER,
    Role.WITCH,
    Role.VILLAGER, Role.VILLAGER,
]


def assign_roles(player_count: int, custom_roles: Optional[List[Role]] = None) -> List[Role]:
    """
    为 N 个玩家分配角色。
    - 如果提供了 custom_roles，使用它（长度必须匹配）
    - 否则自动生成合适的配置
    """
    if custom_roles is not None:
        if len(custom_roles) != player_count:
            raise ValueError(f"角色数 ({len(custom_roles)}) 必须等于玩家数 ({player_count})")
        roles = list(custom_roles)
    else:
        if player_count == 6:
            roles = list(DEFAULT_ROLES_6P)
        elif player_count == 8:
            roles = list(DEFAULT_ROLES_8P)
        else:
            # 自适应：人数/4 个狼人，1预1巫1猎，其余村民
            wolf_count = max(1, player_count // 4)
            roles = [Role.WEREWOLF] * wolf_count
            specials = [Role.SEER, Role.WITCH, Role.HUNTER]
            for r in specials:
                if len(roles) < player_count:
                    roles.append(r)
            while len(roles) < player_count:
                roles.append(Role.VILLAGER)
            roles = roles[:player_count]

    random.shuffle(roles)
    return roles
