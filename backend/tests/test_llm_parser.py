"""
LLM Parser 测试 — 解析 LLM 输出为 AgentAction。
所有测试离线运行，不调用真实 API。
"""
from backend.app.llm.parser import parse_llm_action, LLMParseError
from backend.app.schemas.agent import AgentAction


class TestLLMParser:
    """LLM 输出解析测试"""

    def test_parse_valid_action(self):
        result = parse_llm_action(
            {"action_type": "speak", "target_id": None, "content": "我是好人"},
            actor_id=3,
            legal_actions=["speak", "vote"],
        )
        assert result is not None
        assert result.action_type == "speak"
        assert result.actor_id == 3
        assert result.content == "我是好人"
        assert result.target_id is None
        assert result.metadata.get("source") == "llm"
        assert "reasoning_summary" in result.metadata

    def test_parse_valid_vote(self):
        result = parse_llm_action(
            {"action_type": "vote", "target_id": 5, "content": None},
            actor_id=1,
            legal_actions=["speak", "vote"],
        )
        assert result is not None
        assert result.action_type == "vote"
        assert result.target_id == 5

    def test_parse_none_output(self):
        result = parse_llm_action(None, actor_id=1, legal_actions=["speak"])
        assert result is None

    def test_parse_invalid_action_type(self):
        result = parse_llm_action(
            {"action_type": "invalid_action", "target_id": None, "content": None},
            actor_id=1,
            legal_actions=["speak", "vote"],
        )
        assert result is None

    def test_parse_action_type_not_in_legal(self):
        result = parse_llm_action(
            {"action_type": "werewolf_kill", "target_id": 3, "content": None},
            actor_id=1,
            legal_actions=["speak", "vote"],
        )
        assert result is None

    def test_parse_target_id_as_string(self):
        result = parse_llm_action(
            {"action_type": "vote", "target_id": "5", "content": None},
            actor_id=1,
            legal_actions=["vote"],
        )
        assert result is not None
        assert result.target_id == 5

    def test_parse_target_id_as_null(self):
        result = parse_llm_action(
            {"action_type": "speak", "target_id": None, "content": "hi"},
            actor_id=1,
            legal_actions=["speak"],
        )
        assert result is not None
        assert result.target_id is None

    def test_metadata_does_not_contain_api_key(self):
        result = parse_llm_action(
            {"action_type": "speak", "target_id": None, "content": "hi"},
            actor_id=1,
            legal_actions=["speak"],
        )
        md = result.metadata
        assert "api_key" not in str(md)
        assert "API_KEY" not in str(md)
        assert "sk-" not in str(md)
