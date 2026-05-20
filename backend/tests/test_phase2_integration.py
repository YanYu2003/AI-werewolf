"""
Phase 2 — 集成测试
使用 AgentService 自动运行完整对局，验证全流程。
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.game_engine import WerewolfGameEngine
from app.agents.factory import create_agents_for_game
from app.services.agent_service import AgentService
from app.schemas.models import GamePhase, Role, Team


PLAYERS = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]


class TestAgentIntegration:
    """Agent 驱动的完整对局测试"""

    def test_agent_game_produces_winner(self):
        """使用 Agent 自动跑完整局，最终产生 winner_team"""
        engine = WerewolfGameEngine(game_id=1, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        assert "winner_team" in result
        assert result["winner_team"] in ("villagers", "wolves", None)
        assert result["rounds"] >= 1

    def test_game_over_action_present(self):
        """最终产生 game_over action"""
        engine = WerewolfGameEngine(game_id=2, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        found_game_over = False
        for log_entry in result["logs"]:
            for action in log_entry["actions"]:
                if action.get("action_type") == "game_over":
                    found_game_over = True
                    assert action["actor_id"] == 0
                    break
        if result["winner_team"] is not None:
            assert found_game_over, "game_over action should exist when game ends"

    def test_logs_contain_speak(self):
        """logs 中包含 speak action"""
        engine = WerewolfGameEngine(game_id=3, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        found_speak = False
        for log_entry in result["logs"]:
            for action in log_entry["actions"]:
                if action.get("action_type") == "speak":
                    found_speak = True
                    assert action["actor_id"] != 0
                    break
        assert found_speak, "logs should contain speak actions"

    def test_logs_contain_vote(self):
        """logs 中包含 vote action"""
        engine = WerewolfGameEngine(game_id=4, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        found_vote = False
        for log_entry in result["logs"]:
            for action in log_entry["actions"]:
                if action.get("action_type") == "vote":
                    found_vote = True
                    assert action["actor_id"] != 0
                    break
        assert found_vote, "logs should contain vote actions"

    def test_logs_contain_night_actions(self):
        """logs 中包含夜晚行动"""
        engine = WerewolfGameEngine(game_id=5, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        night_actions = {"werewolf_kill", "seer_investigate", "witch_action"}
        found = set()
        for log_entry in result["logs"]:
            for action in log_entry["actions"]:
                if action.get("action_type") in night_actions:
                    found.add(action["action_type"])
        assert len(found) > 0, "logs should contain night actions"

    def test_logs_round_not_duplicate(self):
        """logs 中 round 不重复"""
        engine = WerewolfGameEngine(game_id=6, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        round_nums = [e["round"] for e in result["logs"]]
        assert len(round_nums) == len(set(round_nums)), \
            f"duplicate rounds: {round_nums}"

    def test_logs_json_serializable(self):
        """所有日志 JSON 可序列化"""
        engine = WerewolfGameEngine(game_id=7, player_names=PLAYERS)
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)
        result = svc.run_full_game()

        json_str = json.dumps(result, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert "game_id" in parsed
        assert "logs" in parsed
        assert "winner_team" in parsed


class TestAgentServiceEdgeCases:
    """AgentService 边界情况测试"""

    def test_create_service_without_agents(self):
        """不传 agents 时自动创建"""
        engine = WerewolfGameEngine(game_id=10, player_names=["A", "B", "C", "D", "E", "F"])
        svc = AgentService(engine)
        assert len(svc.agents) == 6

    def test_service_called_on_ended_game(self):
        """游戏结束后调用 services 不报错"""
        engine = WerewolfGameEngine(game_id=11, player_names=["A", "B", "C", "D", "E", "F"])
        agents = create_agents_for_game(engine.players)
        svc = AgentService(engine, agents)

        # 强制结束
        for p in engine.players:
            if p.role == Role.WEREWOLF:
                p.alive = False
        engine._check_winner()

        result = svc.run_full_game()
        assert result["winner_team"] is not None
