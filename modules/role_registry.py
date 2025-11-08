from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

logger = logging.getLogger("role_registry")


@dataclass
class RoleChannelConfig:
    role_id: str
    display_name: str
    voice_id: str
    stt_model: Optional[str] = None
    max_sessions: int = 3
    priority: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class RoleChannelState:
    config: RoleChannelConfig
    active_sessions: Set[str] = field(default_factory=set)
    emotion_state: Optional[str] = None


class RoleRegistry:
    """
    Registry that keeps track of available voice roles and their runtime state.

    - Loads configuration from environment variable `GATEWAY_ROLES` (JSON array)
      or falls back to built-in defaults (huangrong, xiaoruan, pipi).
    - Tracks which sessions are using each role to enforce concurrency limits.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._roles: Dict[str, RoleChannelState] = {}
        self._default_role: str = "huangrong"
        self._load_roles()

    def _load_roles(self) -> None:
        raw = os.getenv("GATEWAY_ROLES")
        roles: Dict[str, RoleChannelState] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                for entry in parsed:
                    role_id = entry.get("role_id")
                    voice_id = entry.get("voice_id")
                    display_name = entry.get("display_name", role_id)
                    if not role_id or not voice_id:
                        continue
                    config = RoleChannelConfig(
                        role_id=role_id,
                        display_name=display_name,
                        voice_id=voice_id,
                        stt_model=entry.get("stt_model"),
                        max_sessions=int(entry.get("max_sessions", 3)),
                        priority=int(entry.get("priority", 0)),
                        metadata=entry.get("metadata", {}),
                    )
                    roles[role_id] = RoleChannelState(config=config)
                if roles:
                    self._roles = roles
                    self._default_role = next(iter(sorted(roles.keys(), key=lambda x: roles[x].config.priority)))
                    logger.info("Loaded %d roles from GATEWAY_ROLES", len(roles))
                    return
            except json.JSONDecodeError:
                logger.warning("Failed to parse GATEWAY_ROLES JSON. Falling back to defaults.")

        # Defaults
        default_roles = [
            RoleChannelConfig(
                role_id="huangrong",
                display_name="黃蓉",
                voice_id=os.getenv("VOICE_ID_HUANGRONG", VOICE_ID_DEFAULT("huangrong")),
                priority=0,
            ),
            RoleChannelConfig(
                role_id="xiaoruan",
                display_name="小軟",
                voice_id=os.getenv("VOICE_ID_XIAORUAN", VOICE_ID_DEFAULT("xiaoruan")),
                priority=1,
            ),
            RoleChannelConfig(
                role_id="pipi",
                display_name="皮皮",
                voice_id=os.getenv("VOICE_ID_PIPI", VOICE_ID_DEFAULT("pipi")),
                priority=2,
            ),
        ]
        for config in default_roles:
            self._roles[config.role_id] = RoleChannelState(config=config)
        self._default_role = "huangrong"
        logger.info("Loaded default role registry (%d roles)", len(self._roles))

    def list_roles(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            return {
                role_id: {
                    "role_id": state.config.role_id,
                    "display_name": state.config.display_name,
                    "voice_id": state.config.voice_id,
                    "stt_model": state.config.stt_model,
                    "max_sessions": state.config.max_sessions,
                    "priority": state.config.priority,
                    "active_sessions": len(state.active_sessions),
                    "emotion_state": state.emotion_state,
                }
                for role_id, state in self._roles.items()
            }

    def default_role(self) -> str:
        return self._default_role

    def acquire_role(self, role_id: Optional[str], session_id: str) -> RoleChannelConfig:
        target_role = role_id or self._default_role
        with self._lock:
            state = self._roles.get(target_role)
            if not state:
                raise ValueError(f"role_not_found:{target_role}")
            if len(state.active_sessions) >= state.config.max_sessions:
                raise RuntimeError(f"role_capacity_exceeded:{target_role}")
            state.active_sessions.add(session_id)
            logger.debug("Session %s acquired role %s", session_id, target_role)
            return state.config

    def release_role(self, role_id: str, session_id: str) -> None:
        with self._lock:
            state = self._roles.get(role_id)
            if not state:
                return
            state.active_sessions.discard(session_id)
            if not state.active_sessions:
                state.emotion_state = None
            logger.debug("Session %s released role %s", session_id, role_id)

    def update_emotion_state(self, role_id: str, emotion: Optional[str]) -> None:
        with self._lock:
            state = self._roles.get(role_id)
            if not state:
                return
            state.emotion_state = emotion

    def can_switch(self, new_role_id: str, session_id: str) -> bool:
        with self._lock:
            state = self._roles.get(new_role_id)
            if not state:
                return False
            if session_id in state.active_sessions:
                return True
            return len(state.active_sessions) < state.config.max_sessions

    def switch_role(self, current_role: str, new_role: str, session_id: str) -> RoleChannelConfig:
        if current_role == new_role:
            return self._roles[current_role].config
        with self._lock:
            if new_role not in self._roles:
                raise ValueError(f"role_not_found:{new_role}")
            target_state = self._roles[new_role]
            if len(target_state.active_sessions) >= target_state.config.max_sessions and session_id not in target_state.active_sessions:
                raise RuntimeError(f"role_capacity_exceeded:{new_role}")
            # Release current
            if current_role in self._roles:
                self._roles[current_role].active_sessions.discard(session_id)
            target_state.active_sessions.add(session_id)
            logger.info("Session %s switched role %s -> %s", session_id, current_role, new_role)
            return target_state.config


def VOICE_ID_DEFAULT(name: str) -> str:
    """Helper to provide deterministic fallback voice IDs for defaults."""
    defaults = {
        "huangrong": "VOICE_ID_HUANGRONG_DEFAULT",
        "xiaoruan": "VOICE_ID_XIAORUAN_DEFAULT",
        "pipi": "VOICE_ID_PIPI_DEFAULT",
    }
    return defaults.get(name, "VOICE_ID_DEFAULT")

