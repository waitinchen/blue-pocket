import asyncio

import pytest

from modules.role_registry import RoleRegistry


@pytest.fixture()
def registry() -> RoleRegistry:
    # Ensure deterministic defaults
    return RoleRegistry()


def test_default_role_acquire_and_release(registry: RoleRegistry) -> None:
    session_id = "session-1"
    config = registry.acquire_role(None, session_id)
    assert config.role_id == registry.default_role()
    assert config.voice_id
    registry.release_role(config.role_id, session_id)
    assert registry.list_roles()[config.role_id]["active_sessions"] == 0


def test_role_capacity(registry: RoleRegistry) -> None:
    role_id = registry.default_role()
    for i in range(1, registry.list_roles()[role_id]["max_sessions"] + 1):
        registry.acquire_role(role_id, f"s{i}")
    with pytest.raises(RuntimeError):
        registry.acquire_role(role_id, "overflow-session")


def test_switch_role_success(registry: RoleRegistry) -> None:
    session_id = "session-switch"
    first_config = registry.acquire_role("huangrong", session_id)
    assert first_config.role_id == "huangrong"
    second_config = registry.switch_role("huangrong", "xiaoruan", session_id)
    assert second_config.role_id == "xiaoruan"
    status = registry.list_roles()
    assert status["xiaoruan"]["active_sessions"] == 1
    assert status["huangrong"]["active_sessions"] == 0


@pytest.mark.asyncio
async def test_registry_safe_across_tasks(registry: RoleRegistry) -> None:
    async def acquire_release(role: str, sid: str) -> None:
        await asyncio.to_thread(registry.acquire_role, role, sid)
        await asyncio.sleep(0.01)
        await asyncio.to_thread(registry.release_role, role, sid)

    await asyncio.gather(*(acquire_release("pipi", f"session-{i}") for i in range(3)))
    assert registry.list_roles()["pipi"]["active_sessions"] == 0

