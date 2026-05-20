"""
LLM Agent Fallback 测试 — LLM 失败时回退到启发式 Agent。
所有测试离线运行，不调用真实 API。
"""
from unittest.mock import MagicMock

from backend.app.agents.llm_agent import LLMEnabledAgent
from backend.app.agents.villager_agent import VillagerAgent
from backend.app.agents.seer_agent import SeerAgent
from backend.app.schemas.agent import AgentAction
from backend.app.schemas.models import Role


class MockView:
    """Mock Agent view for testing"""
    def model_dump(self):
        return {
            "self_player": {"player_id": 1, "name": "Test", "role": "villager"},
            "alive_players": [{"player_id": 2, "name": "B"}],
            "dead_players_public": [],
            "phase": "day",
            "round_num": 1,
            "day_stage": "speak",
            "night_stage": None,
        }


class TestLLMAgentFallback:
    """LLM Agent fallback 测试"""

    def setup_method(self):
        self.heuristic = VillagerAgent(player_id=1, role="villager", name="Test")

    def test_no_llm_fallback_to_heuristic(self):
        """没有 LLM 客户端时使用启发式"""
        agent = LLMEnabledAgent(
            player_id=1,
            role="villager",
            name="Test",
            heuristic_agent=self.heuristic,
            llm_client=None,
        )
        view = MockView()
        agent.receive_view(view)
        action = agent.speak()
        assert action is not None
        assert action.actor_id == 1

    def test_llm_fails_fallback_to_heuristic(self):
        """LLM 返回 None 时 fallback 到启发式"""
        mock_client = MagicMock()
        mock_client.complete_json.return_value = None

        agent = LLMEnabledAgent(
            player_id=1,
            role="villager",
            name="Test",
            heuristic_agent=self.heuristic,
            llm_client=mock_client,
            parser_func=lambda x, y, z: None,
            prompt_builder=lambda r, v, l: "prompt",
        )
        view = MockView()
        agent.receive_view(view)
        action = agent.speak()
        assert action is not None
        assert action.metadata.get("source") in ("heuristic", "fallback_skip")

    def test_llm_invalid_json_causes_fallback(self):
        """非法 JSON 时 fallback"""
        mock_client = MagicMock()
        mock_client.complete_json.return_value = {"action_type": None}

        agent = LLMEnabledAgent(
            player_id=1,
            role="villager",
            name="Test",
            heuristic_agent=self.heuristic,
            llm_client=mock_client,
            parser_func=lambda x, y, z: None,
            prompt_builder=lambda r, v, l: "prompt",
        )
        view = MockView()
        agent.receive_view(view)
        action = agent.speak()
        assert action is not None

    def test_llm_valid_action_used(self):
        """LLM 返回合法动作时使用 LLM 输出"""
        mock_client = MagicMock()
        mock_client.complete_json.return_value = {
            "action_type": "speak",
            "target_id": None,
            "content": "我是好人",
            "reasoning_summary": "简单推理",
        }

        from backend.app.llm.parser import parse_llm_action

        agent = LLMEnabledAgent(
            player_id=1,
            role="villager",
            name="Test",
            heuristic_agent=self.heuristic,
            llm_client=mock_client,
            parser_func=parse_llm_action,
            prompt_builder=lambda r, v, l: "prompt",
        )
        view = MockView()
        agent.receive_view(view)
        action = agent.speak()
        assert action is not None
        assert action.action_type == "speak"
        assert action.content == "我是好人"
        assert action.metadata.get("source") == "llm"

    def test_action_goes_through_validator(self):
        """AgentAction 可以通过 action_validator"""
        from backend.app.engine.action_validator import validate_agent_action
        from backend.app.engine.game_engine import WerewolfGameEngine

        action = AgentAction(
            actor_id=1,
            action_type="speak",
            target_id=None,
            content="hi",
        )
        engine = WerewolfGameEngine(1, ["A", "B", "C", "D", "E", "F", "G", "H"])
        # speak 可能在白天时才合法
        valid, reason = validate_agent_action(engine, action)
        # 不一定合法（取决于阶段），但我们测试的是函数不抛异常
        assert isinstance(valid, bool)
        assert isinstance(reason, str)
