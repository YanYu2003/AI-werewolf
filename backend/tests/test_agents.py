"""
Phase 2 — Agent 接口测试
覆盖每种角色 Agent 的实例化、视角接收、决策输出。
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.base import BaseAgent
from app.agents.werewolf_agent import WerewolfAgent
from app.agents.seer_agent import SeerAgent
from app.agents.witch_agent import WitchAgent
from app.agents.hunter_agent import HunterAgent
from app.agents.villager_agent import VillagerAgent
from app.agents.factory import create_agent, create_agents_for_game
from app.engine.game_engine import WerewolfGameEngine
from app.schemas.agent import AgentView, AgentAction, SelfPlayerInfo, PublicPlayerInfo
from app.schemas.models import Role


class TestAgentInstantiation:
    """每种角色 Agent 都能实例化"""

    def test_create_werewolf_agent(self):
        agent = WerewolfAgent(player_id=1)
        assert agent.player_id == 1
        assert agent.role == "werewolf"

    def test_create_seer_agent(self):
        agent = SeerAgent(player_id=2)
        assert agent.player_id == 2
        assert agent.role == "seer"

    def test_create_witch_agent(self):
        agent = WitchAgent(player_id=3)
        assert agent.player_id == 3
        assert agent.role == "witch"

    def test_create_hunter_agent(self):
        agent = HunterAgent(player_id=4)
        assert agent.player_id == 4
        assert agent.role == "hunter"

    def test_create_villager_agent(self):
        agent = VillagerAgent(player_id=5)
        assert agent.player_id == 5
        assert agent.role == "villager"

    def test_create_via_factory(self):
        """使用 factory 创建 Agent"""
        agents = []
        for role in [Role.WEREWOLF, Role.SEER, Role.WITCH, Role.HUNTER, Role.VILLAGER]:
            agent = create_agent(player_id=1, role=role)
            assert isinstance(agent, BaseAgent)
            agents.append(agent)
        assert len(agents) == 5

    def test_factory_create_for_game(self):
        """为一局游戏创建所有 Agent"""
        engine = WerewolfGameEngine(game_id=1, player_names=["A", "B", "C", "D", "E", "F"])
        agents = create_agents_for_game(engine.players)
        assert len(agents) == 6
        for pid, agent in agents.items():
            assert isinstance(agent, BaseAgent)
            assert agent.player_id == pid


class TestAgentReceivesView:
    """每种 Agent 都能 receive_view"""

    def make_dummy_view(self, player_id=1, role="villager"):
        return AgentView(
            game_id=1,
            round=1,
            phase="day",
            self_player=SelfPlayerInfo(player_id=player_id, name="Test", role=role, alive=True),
            public_players=[PublicPlayerInfo(player_id=i, name=f"P{i}", alive=True) for i in range(1, 7)],
            legal_actions=["speak", "vote"],
        )

    def test_receive_view(self):
        agent = VillagerAgent(player_id=1)
        view = self.make_dummy_view()
        agent.receive_view(view)
        assert agent.get_view() is not None
        assert agent.get_view().self_player.player_id == 1

    def test_werewolf_speak(self):
        agent = WerewolfAgent(player_id=1)
        view = self.make_dummy_view(player_id=1, role="werewolf")
        agent.receive_view(view)
        action = agent.speak()
        assert action.action_type == "speak"
        assert action.actor_id == 1
        assert isinstance(action.content, str)

    def test_seer_night_action(self):
        agent = SeerAgent(player_id=2)
        view = self.make_dummy_view(player_id=2, role="seer")
        agent.receive_view(view)
        action = agent.decide_night_action()
        assert action.action_type == "seer_investigate"
        assert action.actor_id == 2

    def test_villager_night_action_is_skip(self):
        agent = VillagerAgent(player_id=5)
        view = self.make_dummy_view(player_id=5, role="villager")
        agent.receive_view(view)
        action = agent.decide_night_action()
        assert action.action_type == "skip"

    def test_agent_action_json_serializable(self):
        agent = WerewolfAgent(player_id=1)
        action = AgentAction(actor_id=1, action_type="werewolf_kill", target_id=3)
        json_str = json.dumps(action.model_dump())
        parsed = json.loads(json_str)
        assert parsed["actor_id"] == 1
        assert parsed["action_type"] == "werewolf_kill"
