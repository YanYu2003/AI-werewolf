"""
LLM 驱动 Agent — 包装启发式 Agent，优先调用 LLM，失败时 fallback。
"""
from __future__ import annotations

import logging
from typing import Any

from ..schemas.agent import AgentAction
from .base import BaseAgent

logger = logging.getLogger(__name__)


class LLMEnabledAgent(BaseAgent):
    """
    LLM-prioritizing Agent 包装器。
    如果 LLM 客户端可用，优先调用 LLM 决策；否则 fallback 到启发式 Agent。
    """

    def __init__(
        self,
        player_id: int,
        role: str,
        name: str,
        heuristic_agent: BaseAgent,
        llm_client=None,
        prompt_builder=None,
        parser_func=None,
    ):
        super().__init__(player_id=player_id, role=role, name=name)
        self._heuristic = heuristic_agent
        self._llm = llm_client
        self._build_prompt = prompt_builder
        self._parse_action = parser_func

    def _decide_with_llm(self, view, legal_actions: list[str]) -> AgentAction | None:
        """尝试用 LLM 决策，失败返回 None"""
        if not self._llm or not self._build_prompt or not self._parse_action:
            return None

        try:
            from ..llm.prompts import build_system_prompt, build_instruction_prompt, build_agent_view_safe

            safe_view_str = build_agent_view_safe(view.model_dump() if hasattr(view, 'model_dump') else view)
            system = build_system_prompt()
            instruction = build_instruction_prompt(self.role, safe_view_str, legal_actions)

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": instruction},
            ]

            llm_output = self._llm.complete_json(messages)
            if llm_output is None:
                return None

            action = self._parse_action(llm_output, self.player_id, legal_actions)
            if action is None:
                return None

            if action.metadata is not None:
                action.metadata["source"] = "llm"
            return action
        except Exception as e:
            logger.warning("LLM decision failed for %s: %s", self.role, str(e))
            return None

    def _fallback_action(self, method: str, view) -> AgentAction | None:
        """fallback 到启发式 Agent"""
        try:
            self._heuristic.receive_view(view)
            action = getattr(self._heuristic, method)()
            if action is not None:
                if action.metadata is not None:
                    action.metadata["source"] = "heuristic"
                else:
                    from copy import copy as _copy
                    import copy
                    try:
                        action = copy.replace(action, metadata={"source": "heuristic"})
                    except Exception:
                        pass
            return action
        except Exception as e:
            logger.warning("Heuristic fallback failed: %s", str(e))
            return None

    def receive_view(self, view) -> None:
        """接收视角，传递给 heuristic agent"""
        super().receive_view(view)
        self._heuristic.receive_view(view)

    def _get_legal_actions(self, default: list[str]) -> list[str]:
        """获取 legal_actions，优先使用 view.legal_actions"""
        if self._view and hasattr(self._view, 'legal_actions'):
            from_view = self._view.legal_actions
            if from_view and len(from_view) > 0:
                return list(from_view)
        return default

    # ── 各阶段决策方法 ──

    def decide_night_action(self) -> AgentAction:
        view = self._view
        default_legal = []
        if self.role == "werewolf":
            default_legal = ["werewolf_kill"]
        elif self.role == "seer":
            default_legal = ["seer_investigate"]
        elif self.role == "witch":
            default_legal = ["witch_action"]
        elif self.role == "hunter":
            default_legal = ["hunter_shot"]
        legal = self._get_legal_actions(default_legal)

        action = self._decide_with_llm(view, legal)
        if action:
            return action
        fallback = self._fallback_action("decide_night_action", view)
        if fallback:
            return fallback
        return AgentAction(
            actor_id=self.player_id,
            action_type="skip",
            target_id=None,
            content=None,
            metadata={"source": "fallback_skip"},
        )

    def speak(self) -> AgentAction:
        view = self._view
        legal = self._get_legal_actions(["speak"])
        action = self._decide_with_llm(view, legal)
        if action:
            return action
        fallback = self._fallback_action("speak", view)
        if fallback:
            return fallback
        return AgentAction(
            actor_id=self.player_id,
            action_type="speak",
            target_id=None,
            content="...",
            metadata={"source": "fallback_skip"},
        )

    def decide_vote(self) -> AgentAction:
        view = self._view
        legal = self._get_legal_actions(["vote"])
        action = self._decide_with_llm(view, legal)
        if action:
            return action
        fallback = self._fallback_action("decide_vote", view)
        if fallback:
            return fallback
        return AgentAction(
            actor_id=self.player_id,
            action_type="vote",
            target_id=None,
            content=None,
            metadata={"source": "fallback_skip"},
        )

    def decide_hunter_shot(self) -> AgentAction:
        view = self._view
        legal = self._get_legal_actions(["hunter_shot", "hunter_skip"])
        action = self._decide_with_llm(view, legal)
        if action:
            return action
        fallback = self._fallback_action("decide_hunter_shot", view)
        if fallback:
            return fallback
        return AgentAction(
            actor_id=self.player_id,
            action_type="hunter_skip",
            target_id=None,
            content=None,
            metadata={"source": "fallback_skip"},
        )
