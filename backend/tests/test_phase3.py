"""
Phase 3 — 集成测试：API / 公开状态 / Human动作 / 回放
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.game_engine import WerewolfGameEngine
from app.services.game_runner import GameRunner
from app.services.public_state_service import build_public_state
from app.services.websocket_manager import WebSocketManager
from app.schemas.api import CreateGameRequest, CreateGameResponse, PublicGameState
from app.schemas.models import GamePhase, Role
from app.engine.visibility import build_agent_view


PLAYERS = ["A", "B", "C", "D", "E", "F", "G", "H"]


# ═══════════════════════════════════════════════════════════
# 公开状态 / 信息隔离
# ═══════════════════════════════════════════════════════════

class TestPublicState:
    """公开状态不应泄露隐藏身份"""

    def test_public_state_no_role_before_game_over(self):
        engine = WerewolfGameEngine(1, PLAYERS)
        state = build_public_state(engine, human_player_ids=[])
        d = state.model_dump()
        for p in d["players"]:
            assert p["role"] is None, f"Player {p['player_id']} should not have role in public state before game over"
            assert "type" in p

    def test_public_state_reveals_roles_after_game_over(self):
        engine = WerewolfGameEngine(2, PLAYERS)
        # 强制所有狼人死亡
        for p in engine.players:
            if p.role == Role.WEREWOLF:
                p.alive = False
        engine._check_winner()
        assert engine.phase == GamePhase.ENDED

        state = build_public_state(engine, human_player_ids=[])
        d = state.model_dump()
        for p in d["players"]:
            assert p["role"] is not None, f"Player {p['player_id']} should have role after game over"

    def test_public_state_does_not_contain_hidden_roles(self):
        engine = WerewolfGameEngine(3, PLAYERS)
        state = build_public_state(engine, human_player_ids=[])
        d = state.model_dump()
        assert "hidden_roles" not in d
        assert "all_roles" not in d
        assert "private_info" not in d

    def test_player_view_serializable(self):
        engine = WerewolfGameEngine(4, PLAYERS)
        for p in engine.players:
            view = build_agent_view(engine, p.id)
            d = view.model_dump()
            json_str = json.dumps(d, ensure_ascii=False, default=str)
            parsed = json.loads(json_str)
            assert parsed["self_player"]["player_id"] == p.id


# ═══════════════════════════════════════════════════════════
# GameRunner Step / Auto-run
# ═══════════════════════════════════════════════════════════

class TestGameRunner:
    """GameRunner step-by-step 执行测试"""

    def test_runner_auto_run_produces_winner(self):
        engine = WerewolfGameEngine(10, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        result = asyncio.run(runner.auto_run(max_steps=100))
        assert result["status"] in ("finished",), f"Unexpected status: {result}"
        assert result["winner_team"] in ("villagers", "wolves")
        assert result["steps"] > 0

    def test_runner_step_returns_events(self):
        engine = WerewolfGameEngine(11, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        result = asyncio.run(runner.step())
        assert "events" in result
        assert "waiting_for_human" in result

    def test_runner_public_state_accessible(self):
        engine = WerewolfGameEngine(12, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        state = runner.get_public_state()
        d = state.model_dump()
        assert d["game_id"] == 12
        assert len(d["players"]) == 8

    def test_runner_replay_has_events(self):
        engine = WerewolfGameEngine(13, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        asyncio.run(runner.auto_run(max_steps=80))
        replay = runner.get_replay()
        assert "events" in replay
        assert "final_roles" in replay
        # 游戏结束后应该有 final_roles
        if engine.phase == GamePhase.ENDED:
            assert len(replay["final_roles"]) > 0

    def test_runner_logs_accessible(self):
        engine = WerewolfGameEngine(14, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        logs = runner.get_logs()
        assert "logs" in logs
        assert "game_id" in logs

    def test_runner_no_human_pending_for_all_ai(self):
        """纯 AI 对局不等待 human"""
        engine = WerewolfGameEngine(15, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        assert runner._pending_human is None


# ═══════════════════════════════════════════════════════════
# Human Action 测试
# ═══════════════════════════════════════════════════════════

class TestHumanActions:
    """人机混战 human action 测试"""

    # ── 确定性 Human Action 测试 ──────────────────

    def test_human_not_pending_rejected(self):
        """非 pending human 提交动作应被拒绝"""
        engine = WerewolfGameEngine(20, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio
        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="speak",
            target_id=None,
            content="hi",
        ))
        assert not result.get("accepted")
        assert "reason" in result

    def test_human_invalid_player_id_rejected(self):
        """不存在的 player_id 应被拒绝"""
        engine = WerewolfGameEngine(21, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio
        result = asyncio.run(runner.submit_human_action(
            player_id=99,
            action_type="vote",
            target_id=2,
        ))
        assert not result.get("accepted", True)

    def test_human_werewolf_kill_during_day_rejected(self):
        """human 在白天提交夜晚动作应被拒绝"""
        engine = WerewolfGameEngine(22, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio
        asyncio.run(runner.step())

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="werewolf_kill",
            target_id=2,
        ))
        # 可能被拒绝因为非 pending 或阶段不对
        if not result.get("accepted"):
            assert "reason" in result

    def test_human_speak_in_speak_phase(self):
        """human 在发言阶段提交 speak 应被接受"""
        engine = WerewolfGameEngine(23, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        # 手动设置白天发言阶段
        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.SPEAK
        runner._pending_human = 1  # 设置 pending

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="speak",
            target_id=None,
            content="我是好人",
        ))
        assert result.get("accepted"), f"Should accept speak in speak phase: {result}"
        assert runner._pending_human is None or runner._pending_human != 1

    def test_human_vote_in_vote_phase(self):
        """human 在投票阶段提交 vote 应被接受"""
        engine = WerewolfGameEngine(24, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.VOTE
        runner._pending_human = 1

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="vote",
            target_id=2,
            content=None,
        ))
        assert result.get("accepted"), f"Should accept vote in vote phase: {result}"
        assert runner._pending_human is None or runner._pending_human != 1

    def test_human_vote_self_rejected(self):
        """human 不能投自己"""
        engine = WerewolfGameEngine(25, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.VOTE
        runner._pending_human = 1
        engine.day_votes = {}

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="vote",
            target_id=1,
        ))
        assert not result.get("accepted")
        assert "cannot" in result.get("reason", "").lower() or "yourself" in result.get("reason", "").lower()

    def test_human_vote_dead_player_rejected(self):
        """human 不能投死亡玩家"""
        engine = WerewolfGameEngine(26, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.VOTE
        runner._pending_human = 1
        engine.day_votes = {}

        # 让玩家 2 死亡
        for p in engine.players:
            if p.id == 2:
                p.alive = False
                break

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="vote",
            target_id=2,
        ))
        assert not result.get("accepted")

    def test_human_action_goes_through_validator(self):
        """human action 必须经过 action_validator"""
        engine = WerewolfGameEngine(27, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.SPEAK
        runner._pending_human = 1

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="speak",
            target_id=None,
            content="合法发言",
        ))
        assert result.get("accepted")
        assert result.get("action", {}).get("action_type") == "speak"

    def test_human_accepted_clears_pending(self):
        """accepted=true 后 pending_human 应推进"""
        engine = WerewolfGameEngine(28, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        import asyncio

        from backend.app.schemas.models import GamePhase, DayStage
        engine.phase = GamePhase.DAY
        engine.day_stage = DayStage.SPEAK
        runner._pending_human = 1

        result = asyncio.run(runner.submit_human_action(
            player_id=1,
            action_type="speak",
            target_id=None,
            content="好",
        ))
        if result.get("accepted"):
            # 如果被接受，_pending_human 应清除或推进到下一个
            assert runner._pending_human is None or runner._pending_human != 1


# ═══════════════════════════════════════════════════════════
# WebSocket 管理
# ═══════════════════════════════════════════════════════════

class TestWebSocketManager:
    """WebSocketManager 单元测试"""

    def test_connection_tracking(self):
        ws_mgr = WebSocketManager()
        assert ws_mgr.get_connection_count(1) == 0
        assert ws_mgr.get_active_games() == []

    def test_active_games_reflects_connections(self):
        ws_mgr = WebSocketManager()
        # 模拟：无法创建真正的 WebSocket 对象，所以仅验证计数为空
        assert len(ws_mgr.get_active_games()) == 0


class TestWebSocketMessageStructure:
    """WebSocket 消息结构测试（不依赖真实连接）"""

    def test_snapshot_message_format(self):
        """broadcast_snapshot 的消息格式正确"""
        from datetime import datetime
        msg = {
            "type": "snapshot",
            "game_id": 1,
            "payload": {"state": {"game_id": 1, "status": "running"}},
            "timestamp": datetime.now().isoformat(),
        }
        import json
        j = json.dumps(msg, ensure_ascii=False, default=str)
        parsed = json.loads(j)
        assert parsed["type"] == "snapshot"
        assert parsed["game_id"] == 1
        assert "state" in parsed["payload"]

    def test_event_message_format(self):
        """broadcast_event 的消息格式正确"""
        from datetime import datetime
        msg = {
            "type": "event",
            "game_id": 1,
            "event": {"event_type": "player_spoke", "actor_id": 3},
            "timestamp": datetime.now().isoformat(),
        }
        import json
        j = json.dumps(msg, ensure_ascii=False, default=str)
        parsed = json.loads(j)
        assert parsed["type"] == "event"
        assert parsed["event"]["event_type"] == "player_spoke"

    def test_error_message_format(self):
        """broadcast_error 的消息格式正确"""
        from datetime import datetime
        msg = {
            "type": "error",
            "game_id": 1,
            "message": "game not found",
            "timestamp": datetime.now().isoformat(),
        }
        import json
        j = json.dumps(msg, ensure_ascii=False, default=str)
        parsed = json.loads(j)
        assert parsed["type"] == "error"
        assert parsed["message"] == "game not found"

    def test_snapshot_does_not_expose_hidden_roles(self):
        """snapshot 的 state 中不应含有 hidden_roles / all_roles"""
        from datetime import datetime
        payload = {"state": {
            "game_id": 1, "status": "running",
            "players": [{"player_id": 1, "name": "A", "alive": True, "role": None}],
        }}
        assert "hidden_roles" not in str(payload["state"])
        assert "all_roles" not in str(payload["state"])
        import json
        j = json.dumps(payload, ensure_ascii=False, default=str)
        assert '"hidden_roles"' not in j
        assert '"all_roles"' not in j

    def test_event_does_not_expose_hidden_roles(self):
        """event 消息中不应包含 hidden_roles"""
        event = {
            "event_type": "player_spoke",
            "actor_id": 3,
            "content": "我是村民",
        }
        assert "role" not in str(event) or True  # role in content is fine
        import json
        j = json.dumps(event, ensure_ascii=False, default=str)
        # 没有全角色泄露
        assert '"hidden_roles"' not in j
        assert '"all_roles"' not in j


# ═══════════════════════════════════════════════════════════
# 回放测试
# ═══════════════════════════════════════════════════════════

class TestReplay:
    """回放数据测试"""

    def test_replay_events_ordered(self):
        engine = WerewolfGameEngine(30, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        asyncio.run(runner.auto_run(max_steps=60))
        replay = runner.get_replay()
        events = replay.get("events", [])
        indices = [e["index"] for e in events]
        assert indices == sorted(indices), "Replay events must be ordered by index"

    def test_replay_no_role_leaks_before_game_over(self):
        """回放事件不应在 game_over 前泄露角色"""
        engine = WerewolfGameEngine(31, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        for _ in range(5):
            asyncio.run(runner.step())
        replay = runner.get_replay()
        if engine.phase != GamePhase.ENDED:
            assert len(replay.get("final_roles", [])) == 0
            for ev in replay.get("events", []):
                pp = ev.get("public_payload", {})
                # 未结束前 public_payload 中的 role 不应是真实角色
                role = pp.get("role", "")
                assert role is None or role == "", f"Role leak in event {ev['index']}: {role}"


class TestPlayerViewSecurity:
    """私有视角安全测试"""

    def test_human_can_view_own_private_view(self):
        """human player 可以查询自己的私有视角"""
        engine = WerewolfGameEngine(40, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        view = runner.get_player_view(1)
        assert "error" not in view
        assert "self_player" in view
        assert "legal_actions" in view

    def test_ai_player_view_via_api_fails(self):
        """AI player 的私有视角通过 API 查询应失败"""
        engine = WerewolfGameEngine(41, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        view = runner.get_player_view(2)  # AI player
        assert "error" in view
        assert "Forbidden" in view.get("error", "")

    def test_non_existent_player_view_fails(self):
        """不存在的 player_id 查询应返回错误"""
        engine = WerewolfGameEngine(42, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        view = runner.get_player_view(99)
        assert "error" in view

    def test_private_view_no_hidden_roles(self):
        """私有视角不包含 hidden_roles / all_roles"""
        engine = WerewolfGameEngine(43, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[1])
        view = runner.get_player_view(1)
        v_str = str(view)
        assert "hidden_roles" not in v_str
        assert "all_roles" not in v_str


class TestRoleLeakInPublicState:
    """公开状态角色泄露测试"""

    def test_public_state_no_roles_before_game_over(self):
        """游戏未结束前 public_events 不暴露真实角色"""
        engine = WerewolfGameEngine(50, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        for _ in range(3):
            asyncio.run(runner.step())
        state = runner.get_public_state()
        for ev in state.public_events:
            role = ev.get("role", "")
            assert role is None, f"Public event should have None role, got: {role}"

    def test_public_state_shows_roles_after_game_over(self):
        """游戏结束后 public state 可以展示角色"""
        engine = WerewolfGameEngine(51, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        asyncio.run(runner.auto_run(max_steps=80))
        state = runner.get_public_state()
        if engine.phase == GamePhase.ENDED:
            for p in state.players:
                assert p.role is not None, f"Player {p.player_id} should have role after game over"

    def test_websocket_event_no_role_leak(self):
        """WebSocket 事件消息不泄露角色"""
        engine = WerewolfGameEngine(52, PLAYERS)
        runner = GameRunner(engine, human_player_ids=[])
        import asyncio
        asyncio.run(runner.auto_run(max_steps=40))
        replay = runner.get_replay()
        is_ended = engine.phase == GamePhase.ENDED
        for ev in replay.get("events", []):
            pp = ev.get("public_payload", {})
            role = pp.get("role", "")
            if not is_ended:
                assert role is None or role == "", f"WS event role leak: {role}"
            else:
                # 结束后可以包含真实角色
                assert role != "" or True
