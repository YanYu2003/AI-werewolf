"""
Phase 2 — 信息隔离测试
严格验证 AgentView 不包含不应看到的信息。
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.game_engine import WerewolfGameEngine
from app.engine.visibility import build_agent_view
from app.schemas.models import Role


VILLAGER_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]


class TestVisibilityVillager:
    """村民视角测试"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(100, VILLAGER_NAMES)

    def _get_villager(self):
        for p in self.engine.players:
            if p.role == Role.VILLAGER:
                return p
        return None

    def test_villager_view_has_no_role_info(self):
        v = self._get_villager()
        view = build_agent_view(self.engine, v.id)
        for p in view.public_players:
            assert not hasattr(p, "role"), "public_players should not have role field"

    def test_villager_view_no_known_wolves(self):
        v = self._get_villager()
        view = build_agent_view(self.engine, v.id)
        assert len(view.private_info.known_wolves) == 0
        assert len(view.private_info.investigation_results) == 0
        assert view.private_info.tonight_kill_target is None
        assert not view.private_info.has_antidote


class TestVisibilitySeer:
    """预言家视角测试"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(101, VILLAGER_NAMES)

    def _get_seer(self):
        for p in self.engine.players:
            if p.role == Role.SEER:
                return p
        return None

    def test_seer_view_no_global_roles(self):
        seer = self._get_seer()
        view = build_agent_view(self.engine, seer.id)
        # 不能有完整的 hidden_roles
        assert not hasattr(view, "hidden_roles")
        assert not hasattr(view, "all_roles")
        # known_wolves 应该为空
        assert len(view.private_info.known_wolves) == 0

    def test_seer_cannot_see_wolves(self):
        seer = self._get_seer()
        view = build_agent_view(self.engine, seer.id)
        # 村民的 role 字段不应该出现在 public_players 中
        for p in view.public_players:
            assert not hasattr(p, "role")


class TestVisibilityWitch:
    """女巫视角测试"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(102, VILLAGER_NAMES)

    def _get_witch(self):
        for p in self.engine.players:
            if p.role == Role.WITCH:
                return p
        return None

    def test_witch_view_has_potion_info(self):
        witch = self._get_witch()
        view = build_agent_view(self.engine, witch.id)
        # 女巫能看到药水状态
        assert hasattr(view.private_info, "has_antidote")
        assert hasattr(view.private_info, "has_poison")

    def test_witch_view_no_wolves(self):
        witch = self._get_witch()
        view = build_agent_view(self.engine, witch.id)
        assert len(view.private_info.known_wolves) == 0
        assert len(view.private_info.investigation_results) == 0


class TestVisibilityWerewolf:
    """狼人视角测试"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(103, VILLAGER_NAMES)

    def _get_wolves(self):
        return [p for p in self.engine.players if p.role == Role.WEREWOLF]

    def test_wolf_can_see_teammates(self):
        wolves = self._get_wolves()
        assert len(wolves) >= 2
        wolf1 = wolves[0]
        view = build_agent_view(self.engine, wolf1.id)
        assert len(view.private_info.known_wolves) > 0
        # 已知狼人中应该有另一个狼人
        for w in wolves[1:]:
            assert w.id in view.private_info.known_wolves

    def test_wolf_view_public_no_role(self):
        wolves = self._get_wolves()
        view = build_agent_view(self.engine, wolves[0].id)
        for p in view.public_players:
            assert not hasattr(p, "role")


class TestVisibilityHunter:
    """猎人视角测试"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(104, VILLAGER_NAMES)

    def _get_hunter(self):
        for p in self.engine.players:
            if p.role == Role.HUNTER:
                return p
        return None

    def test_hunter_view_no_hidden_roles(self):
        hunter = self._get_hunter()
        view = build_agent_view(self.engine, hunter.id)
        assert len(view.private_info.known_wolves) == 0
        assert len(view.private_info.investigation_results) == 0
        for p in view.public_players:
            assert not hasattr(p, "role")


class TestGeneralIsolation:
    """通用隔离规则"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(105, VILLAGER_NAMES)

    def test_agent_view_does_not_contain_hidden_roles(self):
        """AgentView 不应包含完整 hidden_roles 表"""
        for p in self.engine.players:
            view = build_agent_view(self.engine, p.id)
            assert not hasattr(view, "hidden_roles")
            assert not hasattr(view, "all_roles")

    def test_all_views_serializable(self):
        """所有 AgentView 必须可 JSON 序列化"""
        import json
        for p in self.engine.players:
            view = build_agent_view(self.engine, p.id)
            d = view.model_dump()
            json_str = json.dumps(d, ensure_ascii=False, default=str)
            parsed = json.loads(json_str)
            assert parsed["self_player"]["player_id"] == p.id
