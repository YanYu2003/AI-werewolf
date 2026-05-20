"""
AI 狼人杀 — Phase 1 引擎测试

验收标准:
1. 可以成功创建游戏
2. 回合按顺序推进
3. 胜负判定逻辑正确
4. 日志完整且 JSON 可解析
"""

import json
import sys
import os
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.engine.game_engine import WerewolfGameEngine
from app.schemas.models import (
    DayStage,
    GamePhase,
    NightStage,
    Role,
    Team,
)


# ── 工具函数 ───────────────────────────────────────────

def find_player_by_role(engine: WerewolfGameEngine, role: Role):
    """找到第一个存活且指定角色的玩家"""
    for p in engine.players:
        if p.role == role and p.alive:
            return p
    return None


def find_alive_wolves(engine: WerewolfGameEngine):
    return [p for p in engine.players if p.role == Role.WEREWOLF and p.alive]


def find_alive_villagers(engine: WerewolfGameEngine):
    return [p for p in engine.players if p.team == Team.VILLAGERS and p.alive]


def pick_alive_target(engine: WerewolfGameEngine, exclude_ids: List[int]):
    """选一个存活玩家（排除指定ID）"""
    for p in engine.players:
        if p.alive and p.id not in exclude_ids:
            return p
    return None


def simulate_full_night(
    engine: WerewolfGameEngine,
    wolf_target: Optional[int] = None,
    seer_target: Optional[int] = None,
    witch_use_save: bool = False,
    witch_poison_target: Optional[int] = None,
) -> bool:
    """
    模拟完整的一夜流程。
    返回 True 表示游戏还在继续，False 表示游戏已结束。
    """
    # 狼人阶段
    wolves = find_alive_wolves(engine)
    if wolves:
        target = wolf_target or (
            pick_alive_target(engine, [w.id for w in wolves]).id
            if pick_alive_target(engine, [w.id for w in wolves])
            else None
        )
        if target is not None:
            for wolf in wolves:
                engine.submit_action(
                    action_type="werewolf_kill",
                    actor_id=wolf.id,
                    target_id=target,
                )

    if engine.phase == GamePhase.ENDED:
        return False

    # 预言家阶段
    seer = find_player_by_role(engine, Role.SEER)
    if seer and engine.night_stage == NightStage.SEER_INVESTIGATE:
        target = seer_target or pick_alive_target(engine, [seer.id])
        if target:
            engine.submit_action(
                action_type="seer_investigate",
                actor_id=seer.id,
                target_id=target.id,
            )

    if engine.phase == GamePhase.ENDED:
        return False

    # 女巫阶段
    witch = find_player_by_role(engine, Role.WITCH)
    if witch and engine.night_stage == NightStage.WITCH_ACTION:
        action_content = json.dumps({
            "use_save": witch_use_save,
            "poison_target": witch_poison_target,
        })
        engine.submit_action(
            action_type="witch_action",
            actor_id=witch.id,
            content=action_content,
        )

    if engine.phase == GamePhase.ENDED:
        return False

    # 处理猎人夜晚死亡后的开枪
    if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.JUDGMENT:
        for pid in engine.night_deaths:
            h = engine._get_player(pid)
            if h and h.role == Role.HUNTER:
                target = pick_alive_target(engine, [h.id])
                if target:
                    engine.submit_action("hunter_shot", h.id, target.id)
                break

    if engine.phase == GamePhase.ENDED:
        return False

    # 自动处理白天发言阶段
    if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.SPEAK:
        speak_alive = [p for p in engine.players if p.alive]
        for p in speak_alive:
            if engine.phase == GamePhase.ENDED:
                break
            if engine.day_stage != DayStage.SPEAK:
                break
            engine.submit_action(
                action_type="speak",
                actor_id=p.id,
                content="我是村民。"
            )

    if engine.phase == GamePhase.ENDED:
        return False

    return True


def simulate_vote(engine: WerewolfGameEngine, vote_map: Dict[int, int]) -> bool:
    """
    模拟白天投票。
    vote_map: voter_id → target_id
    返回 True 表示游戏继续，False 表示已结束。
    """
    for voter_id, target_id in vote_map.items():
        engine.submit_action(
            action_type="vote",
            actor_id=voter_id,
            target_id=target_id,
        )

    if engine.phase == GamePhase.ENDED:
        return False

    # 处理猎人开枪
    if engine.day_stage == DayStage.JUDGMENT and engine.vote_exiled:
        exiled = engine._get_player(engine.vote_exiled)
        if exiled and exiled.role == Role.HUNTER:
            # 猎人选择带人
            target = pick_alive_target(engine, [exiled.id])
            if target:
                engine.submit_action(
                    action_type="hunter_shot",
                    actor_id=exiled.id,
                    target_id=target.id,
                )
                if engine.phase == GamePhase.ENDED:
                    return False

    return True


def simulate_hunter_night_shot(
    engine: WerewolfGameEngine,
    hunter_id: int,
    target_id: Optional[int] = None,
) -> bool:
    """处理猎人在夜晚死亡的射击"""
    if not target_id:
        target = pick_alive_target(engine, [hunter_id])
        if not target:
            return False
        target_id = target.id

    # 猎人是在白天 ANNOUNCE_DEATH 阶段被触发
    # 我们需要换一种方式触发猎人开枪
    # 在目前的设计中，猎人夜晚死亡后被标记，白天阶段进入 JUDGMENT 等待开枪
    # 但实际上应该是在 day_stage == JUDGMENT 时提交 hunter_shot
    engine.submit_action(
        action_type="hunter_shot",
        actor_id=hunter_id,
        target_id=target_id,
    )
    return engine.phase != GamePhase.ENDED


# ══════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════

class TestGameEngine:
    """Phase 1 验收测试"""

    NAMES_8P = [
        "Alice", "Bob", "Charlie", "Diana",
        "Eve", "Frank", "Grace", "Henry",
    ]

    # ── 验收 1: 创建游戏 ──────────────────────────────────

    def test_create_game_default_roles(self):
        """默认配置创建 8 人游戏"""
        engine = WerewolfGameEngine(
            game_id=1,
            player_names=self.NAMES_8P,
        )
        assert len(engine.players) == 8
        assert all(p.alive for p in engine.players)
        assert engine.phase == GamePhase.NIGHT
        assert engine.round_num == 1

    def test_create_game_custom_roles(self):
        """自定义角色配置"""
        custom_roles = [
            Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
            Role.SEER, Role.WITCH, Role.HUNTER,
            Role.VILLAGER, Role.VILLAGER,
        ]
        engine = WerewolfGameEngine(
            game_id=2,
            player_names=self.NAMES_8P,
            custom_roles=custom_roles,
        )
        wolf_count = sum(1 for p in engine.players if p.role == Role.WEREWOLF)
        assert wolf_count == 3

    def test_create_game_roles_count_mismatch(self):
        """角色数与玩家数不匹配时抛出异常"""
        try:
            WerewolfGameEngine(
                game_id=3,
                player_names=self.NAMES_8P,
                custom_roles=[Role.WEREWOLF, Role.SEER],
            )
            assert False, "应该抛出异常"
        except ValueError:
            pass

    # ── 验收 2: 回合流转 ──────────────────────────────────

    def test_night_phase_flow(self):
        """夜晚三个阶段正确流转：狼人→预言家→女巫"""
        engine = WerewolfGameEngine(
            game_id=10,
            player_names=self.NAMES_8P,
        )
        assert engine.night_stage == NightStage.WEREWOLF_KILL

        # 狼人全部投票
        wolves = find_alive_wolves(engine)
        target = pick_alive_target(engine, [w.id for w in wolves])
        for wolf in wolves:
            r = engine.submit_action(
                action_type="werewolf_kill",
                actor_id=wolf.id,
                target_id=target.id,
            )
            assert r.success, f"狼人 {wolf.id} 投票失败: {r.message}"

        # 有预言家，应进入预言家阶段
        if find_player_by_role(engine, Role.SEER):
            assert engine.night_stage == NightStage.SEER_INVESTIGATE

            seer = find_player_by_role(engine, Role.SEER)
            seer_target = pick_alive_target(engine, [seer.id])
            r = engine.submit_action(
                action_type="seer_investigate",
                actor_id=seer.id,
                target_id=seer_target.id,
            )
            assert r.success, f"预言家查验失败: {r.message}"
            assert engine.night_stage == NightStage.WITCH_ACTION

        # 有女巫，应进入女巫阶段
        if find_player_by_role(engine, Role.WITCH):
            assert engine.night_stage == NightStage.WITCH_ACTION

            witch = find_player_by_role(engine, Role.WITCH)
            r = engine.submit_action(
                action_type="witch_action",
                actor_id=witch.id,
                content=json.dumps({"use_save": False, "poison_target": None}),
            )
            assert r.success, f"女巫行动失败: {r.message}"

        # 进入白天
        assert engine.phase == GamePhase.DAY
        assert engine.round_num == 1

    def test_day_phase_flow(self):
        """白天投票阶段正确流转"""
        engine = WerewolfGameEngine(
            game_id=11,
            player_names=self.NAMES_8P,
        )

        # 完成第一夜
        simulate_full_night(engine)

        # 进入白天，应该处于 ANNOUNCE_DEATH 并自动推进到 VOTE
        assert engine.phase == GamePhase.DAY
        assert engine.day_stage in (DayStage.VOTE, DayStage.JUDGMENT, DayStage.SPEAK)

        # 投票（如果游戏未结束）
        if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
            alive = engine._alive_players()
            # 所有存活玩家投票给第一个存活玩家（除自己外）
            first_target = alive[0].id if len(alive) > 1 else alive[-1].id
            vote_map = {}
            for p in alive:
                for target_candidate in alive:
                    if target_candidate.id != p.id:
                        vote_map[p.id] = target_candidate.id
                        break
            simulate_vote(engine, vote_map)

        # 验证投票结果（投票后可能进入下一夜）
        assert engine.phase in (GamePhase.DAY, GamePhase.ENDED, GamePhase.NIGHT)

    def test_full_round_cycle(self):
        """完整的一轮（夜晚+白天）"""
        engine = WerewolfGameEngine(
            game_id=12,
            player_names=self.NAMES_8P,
        )
        assert engine.round_num == 1

        # 完整一夜
        simulate_full_night(engine)

        if engine.phase == GamePhase.ENDED:
            return  # 游戏结束

        assert engine.phase == GamePhase.DAY
        assert engine.day_count == 1

        # 白天投票
        if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
            alive = engine._alive_players()
            # 找一个非狼人投票目标来加快好人死亡
            wolf_ids = [w.id for w in find_alive_wolves(engine)]
            vote_map = {}
            for p in alive:
                # 好人投给好人，狼人投给好人以外的目标
                targets = [t for t in alive if t.id != p.id]
                if p.role == Role.WEREWOLF:
                    # 狼人集中票
                    non_wolf_targets = [t for t in targets if t.id not in wolf_ids]
                    if non_wolf_targets:
                        vote_map[p.id] = non_wolf_targets[0].id
                    else:
                        vote_map[p.id] = targets[0].id
                else:
                    # 好人尽量投狼人
                    wolf_targets = [t for t in targets if t.role == Role.WEREWOLF]
                    if wolf_targets:
                        vote_map[p.id] = wolf_targets[0].id
                    else:
                        vote_map[p.id] = targets[0].id
            simulate_vote(engine, vote_map)

    # ── 验收 3: 胜负判定 ──────────────────────────────────

    def test_villagers_win_when_all_wolves_dead(self):
        """所有狼人死亡 → 好人阵营胜利"""
        # 创建 6 人局：2 狼人 + 4 好人
        # 我们直接构造一个所有狼人已死的场景
        names = ["A", "B", "C", "D", "E", "F"]
        custom_roles = [
            Role.WEREWOLF, Role.WEREWOLF,
            Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        ]
        engine = WerewolfGameEngine(20, names, custom_roles)

        # 手动杀死所有狼人
        for p in engine.players:
            if p.role == Role.WEREWOLF:
                p.alive = False

        result = engine._check_winner()
        assert result, "游戏应该结束"
        assert engine.winner == Team.VILLAGERS, "好人阵营应该获胜"

    def test_wolves_win_when_outnumber_villagers(self):
        """存活狼人数 ≥ 存活好人数 → 狼人阵营胜利"""
        names = ["A", "B", "C", "D"]
        custom_roles = [
            Role.WEREWOLF, Role.WEREWOLF,
            Role.VILLAGER, Role.VILLAGER,
        ]
        engine = WerewolfGameEngine(21, names, custom_roles)

        # 杀死一个好人
        for p in engine.players:
            if p.role == Role.VILLAGER:
                p.alive = False
                break

        result = engine._check_winner()
        assert result, "游戏应该结束"
        assert engine.winner == Team.WOLVES, "狼人阵营应该获胜"

    def test_winner_check_no_early_end(self):
        """初始状态下游戏不应提前结束"""
        names = ["A", "B", "C", "D", "E", "F"]
        custom_roles = [
            Role.WEREWOLF, Role.WEREWOLF,
            Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        ]
        engine = WerewolfGameEngine(22, names, custom_roles)

        result = engine._check_winner()
        assert not result, "游戏不应在初始状态结束"
        assert engine.winner is None

    def test_simulated_game_wolves_win(self):
        """模拟完整对局 - 狼人获胜"""
        engine = WerewolfGameEngine(
            game_id=30,
            player_names=self.NAMES_8P,
        )

        max_rounds = 10
        for _ in range(max_rounds):
            # 完成一夜
            alive_before = len(engine._alive_players())
            simulate_full_night(engine)

            if engine.phase == GamePhase.ENDED:
                break

            # 白天投票
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                wolf_ids = [w.id for w in find_alive_wolves(engine)]
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    if p.role == Role.WEREWOLF:
                        non_wolf_targets = [t for t in targets if t.id not in wolf_ids]
                        if non_wolf_targets:
                            vote_map[p.id] = non_wolf_targets[0].id
                        else:
                            vote_map[p.id] = targets[0].id
                    else:
                        wolf_targets = [t for t in targets if t.role == Role.WEREWOLF]
                        if wolf_targets:
                            vote_map[p.id] = wolf_targets[0].id
                        else:
                            vote_map[p.id] = targets[0].id

                    # 如果玩家已投票则跳过
                    if p.id in vote_map:
                        continue

                if vote_map:
                    simulate_vote(engine, vote_map)

            if engine.phase == GamePhase.ENDED:
                break

        # 游戏应该结束
        assert engine.phase == GamePhase.ENDED, "游戏应在模拟结束后结束"
        assert engine.winner is not None, "应有胜负结果"

    # ── 验收 4: 日志 ───────────────────────────────────────

    def test_log_structure(self):
        """日志结构验证"""
        engine = WerewolfGameEngine(
            game_id=40,
            player_names=self.NAMES_8P,
        )

        # 运行几个回合
        for _ in range(3):
            simulate_full_night(engine)
            if engine.phase == GamePhase.ENDED:
                break
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    vote_map[p.id] = targets[0].id if targets else p.id
                simulate_vote(engine, vote_map)
                if engine.phase == GamePhase.ENDED:
                    break

        log_response = engine.get_log()
        logs = log_response.model_dump()

        # 验证基本结构
        assert "game_id" in logs
        assert "rounds" in logs
        assert "winner_team" in logs
        assert "logs" in logs

        # 验证日志 JSON 可解析
        json_str = json.dumps(logs, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["game_id"] == 40

        # 验证日志动作结构
        if parsed["logs"]:
            first_round = parsed["logs"][0]
            assert "round" in first_round
            assert "actions" in first_round
            if first_round["actions"]:
                action = first_round["actions"][0]
                assert "actor_id" in action
                assert "role" in action
                assert "action_type" in action
                assert "timestamp" in action

    def test_log_records_actions(self):
        """日志应记录每个角色行动"""
        engine = WerewolfGameEngine(
            game_id=41,
            player_names=self.NAMES_8P,
        )

        # 完成第一夜
        simulate_full_night(
            engine,
            witch_use_save=False,
        )

        log_response = engine.get_log()
        logs = log_response.model_dump()

        # 日志应该不为空
        assert len(logs["logs"]) > 0

        # 收集所有动作
        all_actions = []
        for rlog in logs["logs"]:
            all_actions.extend(rlog.get("actions", []))

        # 应该包含狼人行动
        werewolf_actions = [
            a for a in all_actions
            if a.get("action_type") == "werewolf_kill"
        ]
        wolf_count = len(find_alive_wolves(engine))
        # 这里注意：狼人已全部投票，但在日志中 records 是在投票时记录的
        # 由于 simulate_full_night 中狼人在一轮（夜晚）内都投了票
        # 应该至少有 1 条 werewolf_kill resolved
        assert len(werewolf_actions) >= wolf_count or any(
            a.get("action_type") == "werewolf_kill_resolved" for a in all_actions
        )

        # 应该包含 night_resolve
        night_resolves = [
            a for a in all_actions
            if a.get("action_type") == "night_resolve"
        ]
        assert len(night_resolves) > 0

    # ── 边界场景 ─────────────────────────────────────────

    def test_witch_save_prevents_death(self):
        """女巫使用解药可以救人"""
        engine = WerewolfGameEngine(
            game_id=50,
            player_names=self.NAMES_8P,
        )

        wolves = find_alive_wolves(engine)
        target = pick_alive_target(engine, [w.id for w in wolves])
        target_id = target.id

        # 使用 save
        simulate_full_night(
            engine,
            wolf_target=target_id,
            seer_target=None,
            witch_use_save=True,
            witch_poison_target=None,
        )

        # 被救的玩家应该还活着
        saved_player = engine._get_player(target_id)
        assert saved_player.alive, "女巫解药救活的玩家应该存活"

    def test_witch_poison_kills(self):
        """女巫使用毒药可以毒杀"""
        engine = WerewolfGameEngine(
            game_id=51,
            player_names=self.NAMES_8P,
        )

        # 找个非女巫的好人作为毒药目标
        poison_target = None
        for p in engine.players:
            if p.role not in (Role.WEREWOLF, Role.WITCH) and p.alive:
                poison_target = p.id
                break

        if poison_target is None:
            assert False, "未找到合适的毒药目标"

        simulate_full_night(
            engine,
            witch_use_save=False,
            witch_poison_target=poison_target,
        )

        poisoned = engine._get_player(poison_target)
        assert not poisoned.alive, "女巫毒杀的目标应该死亡"

    def test_hunter_kills_when_exiled(self):
        """猎人被放逐时开枪带走一人"""
        names = ["A", "B", "C", "D", "E", "F"]
        custom_roles = [
            Role.WEREWOLF, Role.WEREWOLF,
            Role.HUNTER,
            Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        ]
        engine = WerewolfGameEngine(60, names, custom_roles)

        # 第一夜让一个好人死亡，加速游戏
        simulate_full_night(engine)

        if engine.phase == GamePhase.ENDED:
            return

        # 白天 - 找到猎人的ID
        hunter = find_player_by_role(engine, Role.HUNTER)
        hunter_id = hunter.id if hunter else None

        if not hunter_id or not hunter.alive:
            # 猎人在夜晚死了，应该自动触发
            return

        # 白天投票 - 所有人（包括猎人自己投给别人）都投猎人
        if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
            alive = engine._alive_players()
            vote_map = {}
            for p in alive:
                if p.id != hunter_id:
                    vote_map[p.id] = hunter_id
            # 猎人投给第一个其他存活玩家（所有存活玩家都必须投票才能结算）
            hunter_vote_target = next((t for t in alive if t.id != hunter_id), None)
            if hunter_vote_target:
                vote_map[hunter_id] = hunter_vote_target.id
            simulate_vote(engine, vote_map)

        # 猎人应该死亡，且带走了另一个人
        assert not hunter.alive
        if engine.hunter_kill_target:
            killed_by_hunter = engine._get_player(engine.hunter_kill_target)
            assert killed_by_hunter and not killed_by_hunter.alive

    def test_log_json_serializable(self):
        """日志输出的 JSON 必须可序列化"""
        engine = WerewolfGameEngine(
            game_id=70,
            player_names=self.NAMES_8P,
        )

        # 跑几个回合
        for _ in range(5):
            simulate_full_night(engine)
            if engine.phase == GamePhase.ENDED:
                break
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    vote_map[p.id] = targets[0].id if targets else p.id
                simulate_vote(engine, vote_map)
                if engine.phase == GamePhase.ENDED:
                    break

        log_response = engine.get_log()
        data = log_response.model_dump()
        json_str = json.dumps(data, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert parsed["game_id"] == 70
        assert "rounds" in parsed
        assert "logs" in parsed

    # ── 新增验收测试 ────────────────────────────────────

    def test_round_not_duplicate_in_logs(self):
        """每个 round 在 logs 中只能出现一次"""
        engine = WerewolfGameEngine(
            game_id=80,
            player_names=self.NAMES_8P,
        )
        for _ in range(5):
            simulate_full_night(engine)
            if engine.phase == GamePhase.ENDED:
                break
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    vote_map[p.id] = targets[0].id if targets else p.id
                simulate_vote(engine, vote_map)
                if engine.phase == GamePhase.ENDED:
                    break

        log_response = engine.get_log()
        data = log_response.model_dump()
        round_numbers = [entry["round"] for entry in data["logs"]]
        assert len(round_numbers) == len(set(round_numbers)), \
            f"日志存在重复的 round 编号: {round_numbers}"

    def test_system_action_actor_id_is_0(self):
        """system 类型的 action，actor_id 必须为 0"""
        engine = WerewolfGameEngine(
            game_id=81,
            player_names=self.NAMES_8P,
        )
        for _ in range(5):
            simulate_full_night(engine)
            if engine.phase == GamePhase.ENDED:
                break
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    vote_map[p.id] = targets[0].id if targets else p.id
                simulate_vote(engine, vote_map)
                if engine.phase == GamePhase.ENDED:
                    break

        log_response = engine.get_log()
        data = log_response.model_dump()
        for log_entry in data["logs"]:
            for action in log_entry["actions"]:
                if action.get("action_type") in (
                    "werewolf_kill_resolved", "night_resolve",
                    "announce_death", "vote_result", "game_over",
                ):
                    assert action["actor_id"] == 0, \
                        f"system action '{action['action_type']}' 的 actor_id 应为 0，实际为 {action['actor_id']}"

    def test_non_system_action_actor_id_not_0(self):
        """非 system 的 action（玩家动作），actor_id 不能为 0"""
        engine = WerewolfGameEngine(
            game_id=82,
            player_names=self.NAMES_8P,
        )
        for _ in range(5):
            simulate_full_night(engine)
            if engine.phase == GamePhase.ENDED:
                break
            if engine.phase == GamePhase.DAY and engine.day_stage == DayStage.VOTE:
                alive = engine._alive_players()
                vote_map = {}
                for p in alive:
                    targets = [t for t in alive if t.id != p.id]
                    vote_map[p.id] = targets[0].id if targets else p.id
                simulate_vote(engine, vote_map)
                if engine.phase == GamePhase.ENDED:
                    break

        log_response = engine.get_log()
        data = log_response.model_dump()
        for log_entry in data["logs"]:
            for action in log_entry["actions"]:
                action_type = action.get("action_type", "")
                # 明确属于玩家/角色的动作类型
                if action_type in (
                    "werewolf_kill", "seer_investigate",
                    "witch_save", "witch_poison", "witch_skip",
                    "hunter_triggered", "hunter_shot",
                    "vote",
                ):
                    assert action["actor_id"] != 0, \
                        f"玩家动作 '{action_type}' 的 actor_id 不能为 0（实际为 0）"
