"""
AI 狼人杀 — 核心对局引擎

状态机驱动，控制夜晚/白天回合流转、角色行动处理、胜负裁决。
提供 submit_action() 接口逐阶段接收决策，自动推进游戏。
"""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.models import (
    ActionResult,
    ActionLog,
    DayStage,
    GameLogResponse,
    GamePhase,
    GameStateResponse,
    NightStage,
    Player,
    Role,
    RoundLog,
    Team,
    assign_roles,
)


class WerewolfGameEngine:
    """
    狼人杀对局引擎（状态机）

    状态流转:
        NIGHT (WEREWOLF_KILL → SEER_INVESTIGATE → WITCH_ACTION)
            → DAY (ANNOUNCE_DEATH → VOTE → JUDGMENT)
            → NIGHT 或 ENDED
    """

    # ── 初始化 ────────────────────────────────────────────────

    def __init__(
        self,
        game_id: int,
        player_names: List[str],
        custom_roles: Optional[List[Role]] = None,
    ):
        self.game_id = game_id
        self._player_id_counter: int = 0

        # ── 玩家 ──
        self.players: List[Player] = self._init_players(player_names, custom_roles)

        # ── 状态机 ──
        self.phase: GamePhase = GamePhase.NIGHT
        self.night_stage: Optional[NightStage] = None
        self.day_stage: Optional[DayStage] = None
        self.round_num: int = 0
        self.day_count: int = 0
        self.winner: Optional[Team] = None

        # ── 夜晚内部状态 ──
        self.werewolf_kills: Dict[int, int] = {}       # actor_id → target_id
        self.night_kill_target: Optional[int] = None    # 狼人最终决定的刀人目标
        self.seer_target: Optional[int] = None          # 预言家查验目标
        self.witch_save_used: bool = False               # 解药是否已用
        self.witch_poison_used: bool = False              # 毒药是否已用
        self.night_deaths: List[int] = []                # 当夜死亡的玩家ID列表
        self.witch_saved_player: Optional[int] = None    # 被女巫救活的玩家ID
        self.seer_result: Optional[Tuple[int, bool]] = None  # (target_id, is_werewolf)

        # ── 白天内部状态 ──
        self.day_votes: Dict[int, int] = {}              # 投票人ID → 被投票人ID
        self.vote_exiled: Optional[int] = None            # 被放逐者ID
        self.hunter_kill_target: Optional[int] = None     # 猎人带走目标
        self.spoken_players: set[int] = set()             # 已发言玩家集合

        # ── 日志 ──
        self.round_logs: List[RoundLog] = []
        self._current_actions: List[ActionLog] = []

        # ── 启动第一夜 ──
        self._start_night()

    # ── 玩家初始化 ──────────────────────────────────────────

    def _next_player_id(self) -> int:
        self._player_id_counter += 1
        return self._player_id_counter

    def _init_players(
        self, player_names: List[str], custom_roles: Optional[List[Role]]
    ) -> List[Player]:
        roles = assign_roles(len(player_names), custom_roles)
        players: List[Player] = []
        for i, name in enumerate(player_names):
            pid = self._next_player_id()
            role = roles[i]
            team = Team.WOLVES if role == Role.WEREWOLF else Team.VILLAGERS
            players.append(
                Player(id=pid, name=name, role=role, team=team, alive=True)
            )
        return players

    # ── 辅助方法 ────────────────────────────────────────────

    def _alive_players(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def _dead_players(self) -> List[Player]:
        return [p for p in self.players if not p.alive]

    def _get_player(self, player_id: int) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def _alive_role_ids(self, role: Role) -> List[int]:
        return [p.id for p in self.players if p.alive and p.role == role]

    def _has_alive_role(self, role: Role) -> bool:
        return any(p.alive and p.role == role for p in self.players)

    def _alive_wolf_ids(self) -> List[int]:
        return self._alive_role_ids(Role.WEREWOLF)

    def _alive_villager_count(self) -> int:
        return sum(1 for p in self.players if p.alive and p.team == Team.VILLAGERS)

    def _alive_wolf_count(self) -> int:
        return sum(1 for p in self.players if p.alive and p.team == Team.WOLVES)

    def _log_action(
        self,
        actor_id: int,
        role: str,
        action_type: str,
        target_id: Optional[int] = None,
        content: Optional[str] = None,
    ) -> None:
        self._current_actions.append(
            ActionLog(
                actor_id=actor_id,
                role=role,
                action_type=action_type,
                target_id=target_id,
                content=content,
                timestamp=datetime.now().isoformat(),
            )
        )

    def _finalize_round_log(self) -> None:
        """将当前轮次积累的动作保存到 round_logs"""
        if self._current_actions:
            self.round_logs.append(
                RoundLog(round=self.round_num, actions=list(self._current_actions))
            )
        self._current_actions = []

    # ── 夜晚流程 ────────────────────────────────────────────

    def _start_night(self) -> None:
        """进入新的夜晚"""
        self.round_num += 1
        self.phase = GamePhase.NIGHT
        self.day_stage = None

        # 重置夜晚状态
        self.werewolf_kills = {}
        self.night_kill_target = None
        self.seer_target = None
        self.night_deaths = []
        self.witch_saved_player = None
        self.seer_result = None
        self.hunter_kill_target = None

        # 重置玩家当夜标记
        for p in self.players:
            p.is_saved = False
            p.is_poisoned = False

        self._current_actions = []

        # 判断哪些子阶段需要跳过
        if self._alive_wolf_count() > 0:
            self.night_stage = NightStage.WEREWOLF_KILL
        elif self._has_alive_role(Role.SEER):
            self.night_stage = NightStage.SEER_INVESTIGATE
        elif self._has_alive_role(Role.WITCH):
            self.night_stage = NightStage.WITCH_ACTION
        else:
            # 没有特殊角色存活，直接天亮
            self._resolve_night()
            self._start_day()

    def _handle_night_action(
        self, actor: Player, action_type: str, target_id: Optional[int], content: Optional[str]
    ) -> ActionResult:
        if action_type == "werewolf_kill":
            return self._handle_werewolf_kill(actor, target_id, content)
        elif action_type == "seer_investigate":
            return self._handle_seer_investigate(actor, target_id, content)
        elif action_type == "witch_action":
            return self._handle_witch_action(actor, content)
        return ActionResult(success=False, message=f"未知的夜晚行动类型: {action_type}")

    # ── 狼人阶段 ──

    def _handle_werewolf_kill(
        self, actor: Player, target_id: Optional[int], content: Optional[str]
    ) -> ActionResult:
        if self.night_stage != NightStage.WEREWOLF_KILL:
            return ActionResult(success=False, message="当前不是狼人行动阶段")
        if actor.role != Role.WEREWOLF:
            return ActionResult(success=False, message="只有狼人可以进行刀人行动")

        target = self._get_player(target_id) if target_id else None
        if not target or not target.alive:
            return ActionResult(success=False, message=f"目标玩家 {target_id} 不存在或已死亡")
        if target.team == Team.WOLVES:
            return ActionResult(success=False, message="不能刀队友狼人")

        # 记录投票
        self.werewolf_kills[actor.id] = target_id
        self._log_action(
            actor_id=actor.id,
            role="werewolf",
            action_type="werewolf_kill",
            target_id=target_id,
        )

        # 检查是否所有存活狼人都已投票
        alive_wolves = [p for p in self.players if p.alive and p.role == Role.WEREWOLF]
        if len(self.werewolf_kills) >= len(alive_wolves):
            return self._resolve_werewolf_kills()

        return ActionResult(
            success=True,
            message=f"狼人 {actor.name} 投票刀 {target.name}，等待其他狼人投票",
        )

    def _resolve_werewolf_kills(self) -> ActionResult:
        """统计狼人投票，确定最终刀人目标"""
        vote_counts = Counter(self.werewolf_kills.values())
        max_votes = max(vote_counts.values())
        candidates = [pid for pid, cnt in vote_counts.items() if cnt == max_votes]
        kill_target = random.choice(candidates)

        target_player = self._get_player(kill_target)
        self.night_kill_target = kill_target
        self._log_action(
            actor_id=0,
            role="system",
            action_type="werewolf_kill_resolved",
            target_id=kill_target,
            content=f"狼人决定击杀 {target_player.name}(#{kill_target})",
        )

        # 进入下一阶段
        if self._has_alive_role(Role.SEER):
            self.night_stage = NightStage.SEER_INVESTIGATE
            return ActionResult(
                success=True,
                message=f"狼人阶段完成，进入预言家阶段",
                phase_changed=True,
                new_phase="seer_investigate",
            )
        else:
            return self._skip_to_witch()

    def _skip_to_witch(self) -> ActionResult:
        """没有预言家时，跳过到女巫阶段"""
        if self._has_alive_role(Role.WITCH):
            self.night_stage = NightStage.WITCH_ACTION
            return ActionResult(
                success=True,
                message=f"跳过预言家阶段，进入女巫阶段",
                phase_changed=True,
                new_phase="witch_action",
            )
        else:
            # 没有女巫，直接结算夜晚
            self._resolve_night()
            self._start_day()
            return ActionResult(
                success=True,
                message="没有特殊角色存活，直接进入白天",
                phase_changed=True,
                new_phase="day",
            )

    # ── 预言家阶段 ──

    def _handle_seer_investigate(
        self, actor: Player, target_id: Optional[int], content: Optional[str]
    ) -> ActionResult:
        if self.night_stage != NightStage.SEER_INVESTIGATE:
            return ActionResult(success=False, message="当前不是预言家行动阶段")
        if actor.role != Role.SEER:
            return ActionResult(success=False, message="只有预言家可以进行查验")

        target = self._get_player(target_id) if target_id else None
        if not target or not target.alive:
            return ActionResult(success=False, message=f"目标玩家 {target_id} 不存在或已死亡")
        if target.id == actor.id:
            return ActionResult(success=False, message="不能查验自己")

        is_wolf = target.team == Team.WOLVES
        self.seer_target = target_id
        self.seer_result = (target_id, is_wolf)

        result_str = "狼人" if is_wolf else "好人"
        self._log_action(
            actor_id=actor.id,
            role="seer",
            action_type="seer_investigate",
            target_id=target_id,
            content=f"查验 {target.name}: {result_str}",
        )

        # 进入女巫阶段
        if self._has_alive_role(Role.WITCH):
            self.night_stage = NightStage.WITCH_ACTION
            return ActionResult(
                success=True,
                message=f"预言家查验完成：{target.name} 是 {result_str}",
                phase_changed=True,
                new_phase="witch_action",
                extra={"result": result_str},
            )
        else:
            # 没有女巫，直接结算夜晚
            self._resolve_night()
            self._start_day()
            return ActionResult(
                success=True,
                message=f"预言家查验完成：{target.name} 是 {result_str}",
                phase_changed=True,
                new_phase="day",
                extra={"result": result_str},
            )

    # ── 女巫阶段 ──

    def _handle_witch_action(
        self, actor: Player, content: Optional[str]
    ) -> ActionResult:
        if self.night_stage != NightStage.WITCH_ACTION:
            return ActionResult(success=False, message="当前不是女巫行动阶段")
        if actor.role != Role.WITCH:
            return ActionResult(success=False, message="只有女巫可以使用药")

        # content 格式: JSON 字符串 {"use_save": bool, "poison_target": int|null}
        import json

        try:
            data = json.loads(content) if content else {}
        except (json.JSONDecodeError, TypeError):
            return ActionResult(success=False, message="女巫行动格式错误，需要 JSON")

        use_save = data.get("use_save", False)
        poison_target = data.get("poison_target")

        # 处理解药
        if use_save:
            if self.witch_save_used:
                return ActionResult(success=False, message="解药已经用过")
            if not self.night_kill_target:
                return ActionResult(success=False, message="今晚无人被刀，无需使用解药")
            target_player = self._get_player(self.night_kill_target)
            if not target_player or not target_player.alive:
                # 可能已经被毒死...这种情况不该发生，但防御一下
                return ActionResult(success=True, message="目标已死亡，解药无效")
            target_player.is_saved = True
            self.witch_save_used = True
            self.witch_saved_player = self.night_kill_target
            self._log_action(
                actor_id=actor.id,
                role="witch",
                action_type="witch_save",
                target_id=self.night_kill_target,
                content=f"女巫使用解药救活 {target_player.name}(#{self.night_kill_target})",
            )

        # 处理毒药
        if poison_target is not None:
            if self.witch_poison_used:
                return ActionResult(success=False, message="毒药已经用过")
            poison_player = self._get_player(poison_target)
            if not poison_player or not poison_player.alive:
                return ActionResult(success=False, message=f"目标玩家 {poison_target} 不存在或已死亡")
            if poison_player.role == Role.WITCH:
                return ActionResult(success=False, message="女巫不能毒自己")
            poison_player.is_poisoned = True
            self.witch_poison_used = True
            self._log_action(
                actor_id=actor.id,
                role="witch",
                action_type="witch_poison",
                target_id=poison_target,
                content=f"女巫使用毒药毒杀 {poison_player.name}(#{poison_target})",
            )

        if not use_save and poison_target is None:
            self._log_action(
                actor_id=actor.id,
                role="witch",
                action_type="witch_skip",
                target_id=None,
                content="女巫选择不使用任何药",
            )

        # 结算夜晚
        self._resolve_night()
        self._start_day()
        return ActionResult(
            success=True,
            message="女巫行动完成，进入白天",
            phase_changed=True,
            new_phase="day",
        )

    # ── 夜晚结算 ──

    def _resolve_night(self) -> None:
        """结算夜晚：确定死亡名单"""
        self.night_deaths = []

        # 被狼刀且未被女巫救
        if self.night_kill_target is not None:
            victim = self._get_player(self.night_kill_target)
            if victim and victim.alive and not victim.is_saved:
                self.night_deaths.append(victim.id)

        # 被女巫毒杀
        for p in self.players:
            if p.alive and p.is_poisoned:
                if p.id not in self.night_deaths:
                    self.night_deaths.append(p.id)

        # 应用死亡
        for pid in self.night_deaths:
            p = self._get_player(pid)
            if p:
                p.alive = False

        self._log_action(
            actor_id=0,
            role="system",
            action_type="night_resolve",
            target_id=None,
            content=f"夜晚死亡玩家: {self.night_deaths}",
        )

        # 猎人死亡处理：标记等待猎人开枪
        self.hunter_kill_target = None
        for pid in self.night_deaths:
            p = self._get_player(pid)
            if p and p.role == Role.HUNTER:
                self._log_action(
                    actor_id=p.id,
                    role="hunter",
                    action_type="hunter_triggered",
                    target_id=None,
                    content=f"猎人 {p.name}(#{p.id}) 在夜晚死亡，等待开枪",
                )

    def _resolve_hunter_shot(self, actor_id: int, target_id: int) -> ActionResult:
        """猎人开枪带走一人"""
        hunter = self._get_player(actor_id)
        target = self._get_player(target_id)
        if not target or not target.alive:
            return ActionResult(success=False, message="目标不存在或已死亡")

        target.alive = False
        self.hunter_kill_target = target_id
        self._log_action(
            actor_id=actor_id,
            role="hunter",
            action_type="hunter_shot",
            target_id=target_id,
            content=f"猎人 {hunter.name}(#{actor_id}) 开枪带走 {target.name}(#{target_id})",
        )

        return ActionResult(
            success=True,
            message=f"猎人开枪带走了 {target.name}",
            phase_changed=False,
        )

    def _handle_hunter_shot(self, actor_id: int, target_id: Optional[int]) -> ActionResult:
        """处理猎人开枪（允许已死亡的猎人触发）"""
        if self.day_stage != DayStage.JUDGMENT:
            return ActionResult(success=False, message="当前不是猎人开枪阶段")
        hunter = self._get_player(actor_id)
        if not hunter or hunter.role != Role.HUNTER:
            return ActionResult(success=False, message="只有猎人能开枪")
        # 检查猎人是否确实应该触发（被放逐或夜晚死亡）
        if self.vote_exiled != actor_id and actor_id not in self.night_deaths:
            return ActionResult(success=False, message="猎人不能在此时候开枪")
        if target_id is None:
            return ActionResult(success=False, message="请指定开枪目标")
        target = self._get_player(target_id)
        if not target or not target.alive:
            return ActionResult(success=False, message="目标不存在或已死亡")
        result = self._resolve_hunter_shot(actor_id, target_id)
        if not result.success:
            return result
        # 开枪后再检查胜负
        if self._check_winner():
            return ActionResult(
                success=True,
                message=f"猎人带走 {target.name}，游戏结束",
                phase_changed=True,
                new_phase="ended",
            )
        # 判定继续流程：猎人被放逐 → 直接进入下一夜；猎人夜晚死亡 → 白天继续投票
        if self.vote_exiled == actor_id:
            self._finalize_round_log()
            self._start_night()
            return ActionResult(
                success=True,
                message=f"猎人开枪带走 {target.name}，进入下一夜",
                phase_changed=True,
                new_phase="night",
            )
        else:
            # 猎人夜晚死亡，开枪后进入发言阶段
            self.day_stage = DayStage.SPEAK
            return ActionResult(
                success=True,
                message=f"猎人开枪带走 {target.name}，开始白天发言",
                phase_changed=True,
                new_phase="speak",
            )

    # ── 白天流程 ────────────────────────────────────────────

    def _start_day(self) -> None:
        """进入白天"""
        self.phase = GamePhase.DAY
        self.night_stage = None
        self.day_stage = DayStage.ANNOUNCE_DEATH
        self.day_count += 1

        # 重置白天状态
        self.day_votes = {}
        self.vote_exiled = None
        self.spoken_players = set()

        # 先检查胜负
        if self._check_winner():
            return

        # 生成死亡公告
        if not self.night_deaths:
            self._log_action(
                actor_id=0,
                role="system",
                action_type="announce_death",
                target_id=None,
                content="昨晚是平安夜，无人死亡",
            )
        else:
            death_names = [
                self._get_player(pid).name for pid in self.night_deaths
            ]
            self._log_action(
                actor_id=0,
                role="system",
                action_type="announce_death",
                target_id=None,
                content=f"昨晚 {', '.join(death_names)} 死亡",
            )

        # 如果有猎人在夜晚死亡，进入猎人开枪阶段 (JUDGMENT)
        hunter_died = any(
            self._get_player(pid) and self._get_player(pid).role == Role.HUNTER
            for pid in self.night_deaths
        )
        if hunter_died:
            self.day_stage = DayStage.JUDGMENT
        else:
            self.day_stage = DayStage.SPEAK

    # ── 白天发言 ──

    def _handle_speak(self, actor: Player, content: Optional[str]) -> ActionResult:
        """处理白天发言"""
        if self.day_stage != DayStage.SPEAK:
            return ActionResult(success=False, message="当前不是发言阶段")
        if not actor.alive:
            return ActionResult(success=False, message="已死亡玩家不能发言")
        if actor.id in self.spoken_players:
            return ActionResult(success=False, message="你已经发过言了")

        self.spoken_players.add(actor.id)
        self._log_action(
            actor_id=actor.id,
            role=actor.role.value,
            action_type="speak",
            target_id=None,
            content=content or "",
        )

        # 检查是否所有存活玩家都已发言
        alive_ids = {p.id for p in self.players if p.alive}
        if alive_ids.issubset(self.spoken_players):
            self.day_stage = DayStage.VOTE
            return ActionResult(
                success=True,
                message="所有玩家发言完毕，进入投票",
                phase_changed=True,
                new_phase="vote",
            )

        return ActionResult(
            success=True,
            message=f"{actor.name} 发言完成",
        )

    # ── 白天投票 ──

    def _handle_vote(self, actor: Player, target_id: Optional[int], content: Optional[str]) -> ActionResult:
        if self.day_stage != DayStage.VOTE:
            return ActionResult(success=False, message="当前不是投票阶段")
        if not actor.alive:
            return ActionResult(success=False, message="已死亡玩家不能投票")
        if actor.id in self.day_votes:
            return ActionResult(success=False, message="你已经投过票了")
        if target_id is None:
            return ActionResult(success=False, message="请指定投票目标")

        target = self._get_player(target_id)
        if not target or not target.alive:
            return ActionResult(success=False, message=f"目标 {target_id} 不存在或已死亡")
        if target.id == actor.id:
            return ActionResult(success=False, message="不能投自己")

        self.day_votes[actor.id] = target_id
        self._log_action(
            actor_id=actor.id,
            role=actor.role.value,
            action_type="vote",
            target_id=target_id,
            content=f"{actor.name} 投票给 {target.name}",
        )

        # 检查是否所有存活玩家都已投票
        alive_ids = {p.id for p in self.players if p.alive}
        # 如果猎人被放逐，猎人也可以投票吗？标准规则是白天投票时猎人可以投票，被放逐后才开枪
        # 所以所有存活玩家投票
        voted_ids = set(self.day_votes.keys())
        all_voted = alive_ids.issubset(voted_ids)

        if all_voted:
            return self._resolve_vote()

        return ActionResult(
            success=True,
            message=f"{actor.name} 投票完成，等待其他玩家投票",
        )

    def _resolve_vote(self) -> ActionResult:
        """统计投票结果"""
        vote_counts = Counter(self.day_votes.values())
        if not vote_counts:
            self.vote_exiled = None
            self._log_action(
                actor_id=0,
                role="system",
                action_type="vote_result",
                target_id=None,
                content="无人投票，无人被放逐",
            )
        else:
            max_votes = max(vote_counts.values())
            candidates = [pid for pid, cnt in vote_counts.items() if cnt == max_votes]

            if len(candidates) > 1:
                # 平票，无人被放逐
                self.vote_exiled = None
                candidate_names = [self._get_player(pid).name for pid in candidates]
                self._log_action(
                    actor_id=0,
                    role="system",
                    action_type="vote_result",
                    target_id=None,
                    content=f"平票: {', '.join(candidate_names)}，无人被放逐",
                )
            else:
                self.vote_exiled = candidates[0]
                exiled = self._get_player(self.vote_exiled)
                exiled.alive = False
                self._log_action(
                    actor_id=0,
                    role="system",
                    action_type="vote_result",
                    target_id=self.vote_exiled,
                    content=f"{exiled.name}(#{self.vote_exiled}) 被投票放逐",
                )

        # 进入判决阶段
        self.day_stage = DayStage.JUDGMENT

        # 检查胜负
        if self._check_winner():
            return ActionResult(
                success=True,
                message="投票完成，游戏结束",
                phase_changed=True,
                new_phase="ended",
            )

        # 处理放逐后猎人开枪
        if self.vote_exiled:
            exiled = self._get_player(self.vote_exiled)
            if exiled and exiled.role == Role.HUNTER:
                return ActionResult(
                    success=True,
                    message=f"猎人 {exiled.name} 被放逐，等待开枪",
                    phase_changed=True,
                    new_phase="judgment",
                )

        # 没人需要开枪，进入下一夜
        self._finalize_round_log()
        self._start_night()
        return ActionResult(
            success=True,
            message="投票完成，进入下一夜",
            phase_changed=True,
            new_phase="night",
        )

    # ── 胜负判定 ────────────────────────────────────────────

    def _check_winner(self) -> bool:
        """
        检查游戏是否结束。
        - 狼人胜利条件：所有好人都死亡，或存活狼人 >= 存活好人
        - 好人胜利条件：所有狼人已死亡
        """
        wolves_alive = self._alive_wolf_count()
        villagers_alive = self._alive_villager_count()

        if wolves_alive == 0:
            self.winner = Team.VILLAGERS
            self.phase = GamePhase.ENDED
            self._log_action(
                actor_id=0,
                role="system",
                action_type="game_over",
                target_id=None,
                content="好人阵营获胜！所有狼人已被消灭。",
            )
            self._finalize_round_log()
            return True

        if wolves_alive >= villagers_alive:
            self.winner = Team.WOLVES
            self.phase = GamePhase.ENDED
            self._log_action(
                actor_id=0,
                role="system",
                action_type="game_over",
                target_id=None,
                content=f"狼人阵营获胜！存活情况 -> 狼人: {wolves_alive} / 好人: {villagers_alive}",
            )
            self._finalize_round_log()
            return True

        return False

    # ── 主行动入口 ──────────────────────────────────────────

    def submit_action(
        self,
        action_type: str,
        actor_id: int,
        target_id: Optional[int] = None,
        content: Optional[str] = None,
    ) -> ActionResult:
        """
        提交一个行动。

        参数:
            action_type: 动作类型
                - 夜晚: "werewolf_kill", "seer_investigate", "witch_action"
                - 白天: "vote", "hunter_shot"
            actor_id: 执行者玩家ID
            target_id: 目标玩家ID
            content: 额外内容（女巫行动JSON、猎人开枪等）
        """
        if self.phase == GamePhase.ENDED:
            return ActionResult(success=False, message="游戏已结束")

        actor = self._get_player(actor_id)
        if not actor:
            return ActionResult(success=False, message=f"玩家 {actor_id} 不存在")

        # 猎人开枪允许死者操作
        if action_type == "hunter_shot":
            return self._handle_hunter_shot(actor_id, target_id)

        if not actor.alive:
            return ActionResult(success=False, message="已死亡玩家不能行动")

        # 夜晚行动
        if self.phase == GamePhase.NIGHT:
            return self._handle_night_action(actor, action_type, target_id, content)

        # 白天行动
        if self.phase == GamePhase.DAY:
            if action_type == "speak":
                return self._handle_speak(actor, content)
            if action_type == "vote":
                return self._handle_vote(actor, target_id, content)
            return ActionResult(success=False, message=f"未知的白天行动: {action_type}")

        return ActionResult(success=False, message="游戏状态异常")

    # ── 查询接口 ────────────────────────────────────────────

    def get_state(self) -> GameStateResponse:
        """获取当前游戏公共状态"""
        alive_players = [p for p in self.players if p.alive]
        return GameStateResponse(
            game_id=self.game_id,
            phase=self.phase,
            night_stage=self.night_stage,
            day_stage=self.day_stage,
            round_num=self.round_num,
            alive_players=alive_players,
            wolves_alive=self._alive_wolf_count(),
            villagers_alive=self._alive_villager_count(),
            winner=self.winner,
        )

    def get_player_view(self, player_id: int) -> Dict[str, Any]:
        """
        获取某玩家视角的信息。
        - 狼人能看到队友
        - 预言家能看到查验结果（如果有）
        - 女巫能看到被刀的人和药使用情况
        """
        player = self._get_player(player_id)
        if not player:
            return {"error": "玩家不存在"}

        base = {
            "game_id": self.game_id,
            "phase": self.phase.value if self.phase else None,
            "round_num": self.round_num,
            "your_role": player.role.value,
            "your_team": player.team.value,
            "alive_players": [
                {"id": p.id, "name": p.name} for p in self.players if p.alive
            ],
        }

        # 狼人能看到队友
        if player.role == Role.WEREWOLF:
            base["werewolf_teammates"] = [
                {"id": p.id, "name": p.name}
                for p in self.players
                if p.role == Role.WEREWOLF and p.id != player_id and p.alive
            ]

        # 预言家能看到最近的查验结果
        if player.role == Role.SEER and self.seer_result:
            target_id, is_wolf = self.seer_result
            target = self._get_player(target_id)
            if target:
                base["seer_result"] = {
                    "target_id": target_id,
                    "target_name": target.name,
                    "is_werewolf": is_wolf,
                }

        # 女巫能看到今晚被刀的人
        if player.role == Role.WITCH and self.night_kill_target is not None:
            target = self._get_player(self.night_kill_target)
            if target and target.alive:
                base["tonight_kill_target"] = {
                    "id": target.id,
                    "name": target.name,
                }
            base["witch_save_used"] = self.witch_save_used
            base["witch_poison_used"] = self.witch_poison_used

        return base

    def get_log(self) -> GameLogResponse:
        """获取完整游戏日志"""
        # 整合当前轮次未 finalize 的动作
        all_logs = list(self.round_logs)
        if self._current_actions:
            all_logs.append(
                RoundLog(round=self.round_num, actions=list(self._current_actions))
            )
        return GameLogResponse(
            game_id=self.game_id,
            rounds=self.round_num,
            winner_team=self.winner.value if self.winner else None,
            logs=all_logs,
        )

    # ── 高级控制接口 ──────────────────────────────────────────

    def force_end_round(self) -> None:
        """强制结束当前轮次，将未完成的动作保存到日志（用于异常退出）"""
        self._finalize_round_log()

    def advance_to_next_night(self) -> bool:
        """
        跳过当前白天，强制进入下一夜。
        仅用于测试/调试。
        """
        if self.phase != GamePhase.DAY:
            return False
        self._finalize_round_log()
        self._start_night()
        return True
