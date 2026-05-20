"""
Prompt 模板 — 为不同角色构建 LLM prompt。
输入只能是 AgentView 的安全序列化版本。
"""
from __future__ import annotations

from typing import Any


ROLE_DESCRIPTIONS = {
    "villager": "你是村民。你没有任何特殊能力，只能通过白天发言和投票找出狼人。",
    "seer": "你是预言家。每晚可以查验一名玩家的真实身份（狼人/好人）。请利用这个信息帮助好人阵营。",
    "witch": "你是女巫。你有一瓶解药和一瓶毒药。夜晚得知被狼人杀害的玩家后，可以选择使用解药救活，或使用毒药毒杀任意存活玩家。",
    "hunter": "你是猎人。当你被淘汰时可以向一名玩家开枪复仇。",
    "werewolf": "你是狼人。夜晚与同伴协商击杀一名玩家。白天伪装成好人，误导投票，保护狼人同伴。",
}


ROLE_GOALS = {
    "villager": "通过发言和投票找出并淘汰所有狼人。",
    "seer": "查验身份，引导好人投票淘汰狼人，同时隐藏好自己的身份避免被狼人杀害。",
    "witch": "合理使用解药和毒药，保护好人并消灭狼人。",
    "hunter": "被淘汰时开枪带走一名狼人。",
    "werewolf": "隐藏身份，夜晚击杀好人，让狼人数量等于或超过好人。",
}


def build_system_prompt() -> str:
    """系统级 Prompt"""
    return (
        "你是狼人杀游戏中的一个角色 Agent。"
        "你只能根据提供给你的 JSON 视角行动，不能使用未提供的信息。"
        "你必须输出严格 JSON，不要输出 Markdown，不要输出任何解释。"
    )


def build_instruction_prompt(
    role: str,
    agent_view_json: str,
    legal_actions: list[str],
) -> str:
    """根据角色和视角构建 instruction prompt"""
    desc = ROLE_DESCRIPTIONS.get(role, "你是村民。")
    goal = ROLE_GOALS.get(role, "找出狼人。")

    prompt = (
        f"当前你要为角色「{role}」决策。\n\n"
        f"{desc}\n"
        f"你的目标：{goal}\n\n"
        f"你可见的信息如下（JSON）：\n{agent_view_json}\n\n"
        f"当前允许动作：{legal_actions}\n\n"
        "请只输出以下 JSON 格式，不要包含任何其他内容：\n"
        '{\n'
        '  "action_type": "...",\n'
        '  "target_id": null,\n'
        '  "content": "...",\n'
        '  "reasoning_summary": "..."\n'
        '}\n\n'
        "要求：\n"
        "- action_type 必须来自上述 legal_actions。\n"
        "- target_id 必须为 int 或 null。\n"
        "- content 用于 speak 动作时应像玩家发言。\n"
        "- 不要泄露你看不到的信息。\n"
        "- 不要输出 Markdown 格式。\n"
    )
    return prompt


def build_agent_view_safe(view_dict: dict[str, Any]) -> str:
    """
    从 AgentView dict 构建安全的 LLM 输入。
    确保不包含 hidden_roles / all_roles / 完整 GameState。
    """
    # 只保留 LLM 需要看到的字段
    safe = {
        "self_player": view_dict.get("self_player"),
        "alive_players": [
            {"player_id": p.get("player_id"), "name": p.get("name")}
            for p in view_dict.get("alive_players", [])
        ],
        "dead_players_public": view_dict.get("dead_players_public", []),
        "current_phase": view_dict.get("phase"),
        "round_num": view_dict.get("round_num"),
        "day_stage": view_dict.get("day_stage"),
        "night_stage": view_dict.get("night_stage"),
    }
    import json
    return json.dumps(safe, ensure_ascii=False, default=str)
