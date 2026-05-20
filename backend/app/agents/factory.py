"""
AgentFactory — 根据角色创建对应的 Agent 实例
支持 LLM-enabled 模式（可选）
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


def create_agent(
    player_id: int,
    role: Role,
    name: str = "",
    enable_llm: bool = False,
    llm_client=None,
) -> BaseAgent:
    """
    根据角色创建一个 Agent 实例。
    如果 enable_llm=True 且 llm_client 可用，包装为 LLMEnabledAgent。
    """
    cls = _ROLE_AGENT_MAP.get(role)
    if cls is None:
        raise ValueError(f"未知角色: {role}")
    heuristic = cls(player_id=player_id, role=role.value, name=name)

    if enable_llm and llm_client is not None:
        from .llm_agent import LLMEnabledAgent
        from ..llm.parser import parse_llm_action
        from ..llm.prompts import build_instruction_prompt

        def prompt_builder(role_str, view_json, legal_actions):
            from ..llm.prompts import build_system_prompt, build_instruction_prompt
            return build_instruction_prompt(role_str, view_json, legal_actions)

        return LLMEnabledAgent(
            player_id=player_id,
            role=role.value,
            name=name,
            heuristic_agent=heuristic,
            llm_client=llm_client,
            prompt_builder=prompt_builder,
            parser_func=parse_llm_action,
        )

    return heuristic


def create_agents_for_game(
    players: list,
    enable_llm: bool = False,
    llm_client=None,
) -> dict[int, BaseAgent]:
    """
    为一局游戏中的所有玩家创建 Agent。
    返回 {player_id: BaseAgent} 字典。
    """
    agents: dict[int, BaseAgent] = {}
    for p in players:
        agents[p.id] = create_agent(
            p.id, p.role, p.name,
            enable_llm=enable_llm,
            llm_client=llm_client,
        )
    return agents
