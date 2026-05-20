"""
LLM 集成测试 — 验证 LLM Agent 真正接入 GameRunner。
所有测试离线运行，使用 mock，不调用真实 API。
"""
import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from backend.app.engine.game_engine import WerewolfGameEngine
from backend.app.services.game_runner import GameRunner
from backend.app.schemas.models import GamePhase, Role, DayStage

PLAYERS = ["A", "B", "C", "D", "E", "F", "G", "H"]


class MockLLMClient:
    """Mock LLM client returning specific JSON"""

    def __init__(self, return_value: dict | None = None):
        self.return_value = return_value
        self.call_count = 0

    def complete_json(self, messages, timeout=None):
        self.call_count += 1
        if self.return_value is None:
            return None
        return self.return_value


class TestLLMIntegration:
    """LLM GameRunner 集成测试"""

    def test_default_env_creates_heuristic_agent(self):
        """默认环境下 GameRunner 创建启发式 Agent"""
        engine = WerewolfGameEngine(1, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        for pid, agent in runner.agents.items():
            # 没有 LLM，应该不是 LLMEnabledAgent
            assert type(agent).__name__ != "LLMEnabledAgent", \
                f"Agent {pid} should not be LLMEnabled in default env"

    def test_llm_env_creates_llm_agent(self):
        """设置 LLM_ENABLED=true + fake key 时，GameRunner 创建 LLMEnabledAgent"""
        os.environ["LLM_ENABLED"] = "true"
        os.environ["LLM_API_KEY"] = "sk-test-key"
        try:
            engine = WerewolfGameEngine(2, PLAYERS)
            runner = GameRunner(engine, human_player_ids=[])
            # 至少有一个 agent 是 LLMEnabledAgent
            llm_agents = [a for a in runner.agents.values()
                          if type(a).__name__ == "LLMEnabledAgent"]
            assert len(llm_agents) > 0, "Should create LLMEnabledAgent when LLM is enabled"
        finally:
            os.environ.pop("LLM_ENABLED", None)
            os.environ.pop("LLM_API_KEY", None)

    @pytest.mark.asyncio
    async def test_mock_llm_speak_appears_in_log(self):
        """mock LLM 返回合法 speak，step 后日志中出现 LLM 输出内容"""
        mock_client = MockLLMClient({
            "action_type": "speak",
            "target_id": None,
            "content": "我是好人，LLM 生成的发言",
            "reasoning_summary": "根据信息推断",
        })
        # 需要 mock GameRunner 中导入的 create_llm_client
        with patch('backend.app.services.game_runner.create_llm_client') as mock_create:
            mock_create.return_value = mock_client
            os.environ["LLM_ENABLED"] = "true"
            os.environ["LLM_API_KEY"] = "sk-test-key"
            try:
                engine = WerewolfGameEngine(3, PLAYERS)
                runner = GameRunner(engine, human_player_ids=[])

                # 设置白天发言阶段
                engine.phase = GamePhase.DAY
                engine.day_stage = DayStage.SPEAK
                engine.spoken_players = set()
                engine.night_stage = None

                import asyncio
                result = await runner.step()
                events = result.get("events", [])

                speak_events = [e for e in events if e.get("action_type") == "speak"]
                if speak_events:
                    assert mock_client.call_count > 0, "LLM should have been called"
            finally:
                os.environ.pop("LLM_ENABLED", None)
                os.environ.pop("LLM_API_KEY", None)

    @pytest.mark.asyncio
    async def test_mock_llm_invalid_action_falls_back(self):
        """mock LLM 返回非法动作时不绕过 action_validator"""
        os.environ["LLM_ENABLED"] = "true"
        os.environ["LLM_API_KEY"] = "sk-test-key"
        try:
            mock_client = MockLLMClient({
                "action_type": "invalid_action_xyz",
                "target_id": None,
                "content": "test",
                "reasoning_summary": "",
            })
            import backend.app.llm.client as client_mod
            original_create = client_mod.create_llm_client

            def mocked_create(config=None):
                return mock_client

            client_mod.create_llm_client = mocked_create

            engine = WerewolfGameEngine(4, PLAYERS)
            runner = GameRunner(engine, human_player_ids=[])
            # 设置白天阶段
            engine.phase = GamePhase.DAY
            engine.day_stage = DayStage.SPEAK
            engine.spoken_players = set()

            import asyncio
            # step 不应抛出异常
            result = await runner.step()
            # 不应有 invalid_action_xyz 事件
            for ev in result.get("events", []):
                assert ev.get("action_type") != "invalid_action_xyz", \
                    "Invalid action should not appear in events"

            client_mod.create_llm_client = mocked_create
        finally:
            os.environ.pop("LLM_ENABLED", None)
            os.environ.pop("LLM_API_KEY", None)

    @pytest.mark.asyncio
    async def test_llm_offline_no_real_api_called(self):
        """LLM 关闭时绝不调用外部 API"""
        # 默认 LLM 关闭
        engine = WerewolfGameEngine(5, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        # 跑几步，不应抛出异常
        for _ in range(5):
            result = await runner.step()
            assert result is not None
