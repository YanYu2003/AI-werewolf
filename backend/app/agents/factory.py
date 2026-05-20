"""
AgentFactory — 根据角色创建对应的 Agent 实例
"""

from __future__ import annotations

from ..schemas.models import Role
from .base import BaseAgent
from .werewolf_agent import WerewolfAgent
from .seer_agent import SeerAgent
from .witch_agent import WitchAgent
from .hunter_agent import HunterAgent
from .villager_agent import VillagerAgent


_ROLE_AGENT_MAP = {
    Role.WEREWOLF: WerewolfAgent,
    Role.SEER: SeerAgent,
    Role.WITCH: WitchAgent,
    Role.HUNTER: HunterAgent,
    Role.VILLAGER: VillagerAgent,
}


def create_agent(player_id: int, role: Role, name: str = "") -> BaseAgent:
    """
    根据角色创建一个 Agent 实例。
    所有 Agent 共享统一的 BaseAgent 接口。
    """
    cls = _ROLE_AGENT_MAP.get(role)
    if cls is None:
        raise ValueError(f"未知角色: {role}")
    return cls(player_id=player_id, role=role.value, name=name)


def create_agents_for_game(players: list) -> dict[int, BaseAgent]:
    """
    为一局游戏中的所有玩家创建 Agent。
    返回 {player_id: BaseAgent} 字典。
    """
    agents: dict[int, BaseAgent] = {}
    for p in players:
        agents[p.id] = create_agent(p.id, p.role, p.name)
    return agents
