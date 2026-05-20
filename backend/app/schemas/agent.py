"""
Agent 模式定义：AgentView / AgentAction / 信息隔离模型
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── 玩家自视角信息 ──────────────────────────────────

class SelfPlayerInfo(BaseModel):
    """Agent 自己的信息"""
    player_id: int
    name: str
    role: str
    alive: bool


# ── 公开玩家信息（不含隐藏身份）────────────────────

class PublicPlayerInfo(BaseModel):
    """Agent 视角下的其他玩家信息——不含 role"""
    player_id: int
    name: str
    alive: bool


# ── 查验结果 ───────────────────────────────────────

class InvestigationResult(BaseModel):
    """预言家的单次查验结果"""
    target_id: int
    target_name: str
    is_werewolf: bool
    round: int


# ── 私有信息（按角色填充）─────────────────────────

class PrivateInfo(BaseModel):
    """Agent 持有的私有信息"""

    # 狼人
    known_wolves: List[int] = []

    # 预言家
    investigation_results: List[InvestigationResult] = []

    # 女巫
    has_antidote: bool = False
    has_poison: bool = False
    antidote_used: bool = False
    poison_used: bool = False
    tonight_kill_target: Optional[int] = None

    # 猎人
    can_shoot: bool = False


# ── AgentView（信息隔离容器）──────────────────────

class AgentView(BaseModel):
    """
    Agent 视角——隔离后的可见信息。
    任何模块都不应把完整 role 表塞入 AgentView。
    """
    game_id: int
    round: int
    phase: str                          # night / day / ended
    day_stage: Optional[str] = None
    night_stage: Optional[str] = None
    self_player: SelfPlayerInfo
    public_players: List[PublicPlayerInfo]
    public_events: List[Dict[str, Any]] = []
    private_info: PrivateInfo = PrivateInfo()
    legal_actions: List[str] = []


# ── AgentAction（Agent 决策输出）──────────────────

class AgentAction(BaseModel):
    """
    Agent 决策输出。
    actor_id / action_type / target_id / content 与引擎 submit_action 参数对齐。
    """
    actor_id: int
    action_type: str
    target_id: Optional[int] = None
    content: Optional[str] = None
    metadata: dict = {}

    def to_submit_kwargs(self) -> dict:
        """转换为引擎 submit_action 参数"""
        return {
            "action_type": self.action_type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "content": self.content,
        }
