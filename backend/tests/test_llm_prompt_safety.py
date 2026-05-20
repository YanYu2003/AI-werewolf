"""
LLM Prompt 安全测试 — 确保 prompt 不泄露隐藏信息。
所有测试离线运行，不调用真实 API。
使用真实 AgentView 字段。
"""
from backend.app.llm.prompts import (
    build_system_prompt,
    build_instruction_prompt,
    build_agent_view_safe,
    ROLE_DESCRIPTIONS,
    ROLE_GOALS,
)


class TestLLMPromptSafety:
    """Prompt 安全性测试"""

    def test_system_prompt_no_game_state(self):
        prompt = build_system_prompt()
        assert "hidden_roles" not in prompt
        assert "all_roles" not in prompt
        assert "GameState" not in prompt
        assert "json" in prompt.lower()

    def test_instruction_prompt_no_hidden_roles(self):
        safe_view = '{"game_id":1,"round":1,"phase":"day","self_player":{"player_id":1},"public_players":[]}'
        prompt = build_instruction_prompt("villager", safe_view, ["speak"])
        assert "hidden_roles" not in prompt
        assert "all_roles" not in prompt
        assert "speak" in prompt

    def test_agent_view_safe_no_hidden_fields(self):
        """使用真实 AgentView 字段，确保隐藏字段被过滤"""
        full_view = {
            "game_id": 1,
            "round": 1,
            "phase": "day",
            "day_stage": "speak",
            "night_stage": None,
            "self_player": {"player_id": 1, "name": "A", "role": "villager", "alive": True},
            "public_players": [
                {"player_id": 2, "name": "B", "alive": True},
                {"player_id": 3, "name": "C", "alive": True},
            ],
            "public_events": [],
            "private_info": {"known_wolves": []},
            "legal_actions": ["speak", "vote"],
            # 以下是不该出现在安全输出中的字段
            "hidden_roles": {1: "villager", 2: "werewolf"},
            "all_roles": {1: "villager", 2: "werewolf"},
        }
        safe_str = build_agent_view_safe(full_view)
        assert "hidden_roles" not in safe_str, "hidden_roles should be filtered"
        assert "all_roles" not in safe_str, "all_roles should be filtered"
        # public_players 不应包含 role 字段
        assert '"role"' not in safe_str.split('"public_players"')[1].split('"public_events"')[0] if '"public_players"' in safe_str else True

    def test_agent_view_safe_keeps_essential(self):
        """使用真实字段构建的安全视图应保留必要信息"""
        view = {
            "game_id": 1,
            "round": 2,
            "phase": "day",
            "day_stage": "vote",
            "night_stage": None,
            "self_player": {"player_id": 1, "name": "A", "role": "villager", "alive": True},
            "public_players": [{"player_id": 2, "name": "B", "alive": True}],
            "public_events": [{"event_type": "speak", "content": "hi"}],
            "private_info": {},
            "legal_actions": ["vote"],
        }
        safe_str = build_agent_view_safe(view)
        assert "self_player" in safe_str
        assert "public_players" in safe_str
        assert "phase" in safe_str
        assert "legal_actions" in safe_str
        assert "vote" in safe_str
        assert "round" in safe_str

    def test_public_players_no_role(self):
        """public_players 不应包含 role 字段"""
        view = {
            "game_id": 1,
            "round": 1,
            "phase": "day",
            "self_player": {"player_id": 1, "name": "A", "role": "villager", "alive": True},
            "public_players": [
                {"player_id": 2, "name": "B", "alive": True, "role": "werewolf"},
            ],
            "public_events": [],
            "private_info": {},
            "legal_actions": [],
        }
        safe_str = build_agent_view_safe(view)
        # public_players 部分不应包含 "role":
        import json
        safe = json.loads(safe_str)
        for p in safe.get("public_players", []):
            assert "role" not in p, f"public player should not have role field: {p}"

    def test_private_info_limited_to_agent_view(self):
        """private_info 只来自 AgentView"""
        view = {
            "game_id": 1,
            "round": 1,
            "phase": "night",
            "self_player": {"player_id": 1, "name": "A", "role": "werewolf", "alive": True},
            "public_players": [],
            "public_events": [],
            "private_info": {
                "known_wolves": [1, 5],
            },
            "legal_actions": ["werewolf_kill"],
        }
        safe_str = build_agent_view_safe(view)
        import json
        safe = json.loads(safe_str)
        pi = safe.get("private_info", {})
        assert "known_wolves" in pi, "werewolf should see known_wolves"
        # 不应有非法字段
        assert "hidden_roles" not in pi
        assert "all_roles" not in pi

    def test_role_descriptions_no_secrets(self):
        for role, desc in ROLE_DESCRIPTIONS.items():
            assert "api_key" not in desc.lower()
            assert "password" not in desc.lower()
            assert "secret" not in desc.lower()

    def test_role_goals_no_secrets(self):
        for role, goal in ROLE_GOALS.items():
            assert "api_key" not in goal.lower()
