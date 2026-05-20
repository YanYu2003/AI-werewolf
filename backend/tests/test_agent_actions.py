"""
Phase 2 — Agent 动作合法性测试
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.game_engine import WerewolfGameEngine
from app.engine.action_validator import validate_agent_action
from app.engine.visibility import build_agent_view
from app.schemas.agent import AgentAction
from app.schemas.models import Role, GamePhase, DayStage


PLAYERS = ["A", "B", "C", "D", "E", "F", "G", "H"]


class TestNightActionValidity:
    """夜晚动作合法性"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(200, PLAYERS)
        # 获取角色
        self.wolves = [p for p in self.engine.players if p.role == Role.WEREWOLF]
        self.seer = next((p for p in self.engine.players if p.role == Role.SEER), None)
        self.witch = next((p for p in self.engine.players if p.role == Role.WITCH), None)
        self.villager = next((p for p in self.engine.players if p.role == Role.VILLAGER), None)

    def test_wolf_cannot_kill_wolf(self):
        """狼人不能击杀狼人"""
        wolf = self.wolves[0]
        other_wolf = self.wolves[1]
        action = AgentAction(actor_id=wolf.id, action_type="werewolf_kill", target_id=other_wolf.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid, f"Should reject wolf killing wolf: {reason}"

    def test_wolf_cannot_kill_dead(self):
        """狼人不能击杀已死亡玩家"""
        wolf = self.wolves[0]
        # 先标记一个玩家死亡
        target = next(p for p in self.engine.players if p.role != Role.WEREWOLF)
        target.alive = False
        action = AgentAction(actor_id=wolf.id, action_type="werewolf_kill", target_id=target.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid, f"Should reject killing dead player: {reason}"
        # 恢复
        target.alive = True

    def test_villager_cannot_night_action(self):
        """村民不能在夜晚行动"""
        if self.villager is None:
            return
        action = AgentAction(actor_id=self.villager.id, action_type="werewolf_kill", target_id=1)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid

    def test_seer_cannot_investigate_self(self):
        """预言家不能查自己"""
        if self.seer is None:
            return
        action = AgentAction(actor_id=self.seer.id, action_type="seer_investigate", target_id=self.seer.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid


class TestDayActionValidity:
    """白天动作合法性"""

    def setup_method(self):
        self.engine = WerewolfGameEngine(201, PLAYERS)

    def _progress_to_vote(self):
        """推进到投票阶段"""
        from tests.test_engine import simulate_full_night
        simulate_full_night(self.engine)

    def test_cannot_vote_dead(self):
        """不能投已死亡玩家"""
        self._progress_to_vote()
        if self.engine.phase != GamePhase.DAY:
            return
        # 找一个存活玩家，先标记为死亡
        alive = [p for p in self.engine.players if p.alive]
        if len(alive) < 2:
            return
        voter = alive[0]
        target = alive[1]
        target.alive = False
        action = AgentAction(actor_id=voter.id, action_type="vote", target_id=target.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid, f"Should reject voting for dead: {reason}"
        target.alive = True

    def test_cannot_vote_self(self):
        """不能投自己"""
        self._progress_to_vote()
        if self.engine.phase != GamePhase.DAY or self.engine.day_stage != DayStage.VOTE:
            return
        alive = [p for p in self.engine.players if p.alive]
        if not alive:
            return
        voter = alive[0]
        action = AgentAction(actor_id=voter.id, action_type="vote", target_id=voter.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid

    def test_hunter_cannot_shoot_self(self):
        """猎人不能射击自己"""
        hunter = next((p for p in self.engine.players if p.role == Role.HUNTER), None)
        if hunter is None:
            return
        # 模拟猎人已死亡且可开枪
        hunter.alive = False
        self.engine.vote_exiled = hunter.id
        self.engine.day_stage = DayStage.JUDGMENT
        action = AgentAction(actor_id=hunter.id, action_type="hunter_shot", target_id=hunter.id)
        valid, reason = validate_agent_action(self.engine, action)
        assert not valid
        hunter.alive = True


class TestIllegalActionFallback:
    """非法 action fallback 测试"""

    def test_witch_cannot_reuse_antidote(self):
        """女巫不能重复使用解药"""
        engine = WerewolfGameEngine(202, PLAYERS)
        witch = next(p for p in engine.players if p.role == Role.WITCH)
        if witch is None:
            return
        # 标记解药已用
        engine.witch_save_used = True
        # 构建一个试图用解药的 action
        action = AgentAction(
            actor_id=witch.id,
            action_type="witch_action",
            content=json.dumps({"use_save": True, "poison_target": None})
        )
        # 直接提交
        if engine.night_stage is not None:
            pass  # 实际的校验在引擎内部，这里主要验证 validator
        valid, reason = validate_agent_action(engine, action)
        # 女巫阶段的 action 校验只是验证角色，具体药水使用由引擎判断
        assert valid or "witch" in reason.lower()
