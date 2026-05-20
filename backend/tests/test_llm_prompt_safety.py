"""
LLM Prompt 安全测试 — 确保 prompt 不泄露隐藏信息。
所有测试离线运行，不调用真实 API。
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
        safe_view = '{"self_player": {"player_id": 1}, "alive_players": []}'
        prompt = build_instruction_prompt("villager", safe_view, ["speak"])
        assert "hidden_roles" not in prompt
        assert "all_roles" not in prompt
        assert "speak" in prompt

    def test_agent_view_safe_no_hidden_fields(self):
        full_view = {
            "self_player": {"player_id": 1, "name": "A", "role": "villager"},
            "alive_players": [
                {"player_id": 2, "name": "B", "role": "werewolf"},
                {"player_id": 3, "name": "C"},
            ],
            "dead_players_public": [],
            "phase": "day",
            "round_num": 1,
            "day_stage": "speak",
            "night_stage": None,
            "hidden_roles": {1: "villager", 2: "werewolf"},
            "all_roles": {1: "villager", 2: "werewolf"},
            "private_info": "top secret",
        }
        safe_str = build_agent_view_safe(full_view)
        assert "hidden_roles" not in safe_str
        assert "all_roles" not in safe_str
        assert "private_info" not in safe_str
        # 安全版本中的 alive_players 不应包含 role 字段
        assert '"role"' not in safe_str or safe_str.count('"role"') == 1  # self_player.role

    def test_agent_view_safe_keeps_essential(self):
        view = {
            "self_player": {"player_id": 1, "name": "A", "role": "villager"},
            "alive_players": [{"player_id": 2, "name": "B"}],
            "dead_players_public": [],
            "phase": "day",
            "round_num": 1,
        }
        safe_str = build_agent_view_safe(view)
        assert "self_player" in safe_str
        assert "alive_players" in safe_str
        assert "current_phase" in safe_str

    def test_role_descriptions_no_secrets(self):
        for role, desc in ROLE_DESCRIPTIONS.items():
            assert "api_key" not in desc.lower()
            assert "password" not in desc.lower()
            assert "secret" not in desc.lower()

    def test_role_goals_no_secrets(self):
        for role, goal in ROLE_GOALS.items():
            assert "api_key" not in goal.lower()
