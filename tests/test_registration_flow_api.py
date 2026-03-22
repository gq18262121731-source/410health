from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_care_service, get_device_service, get_relation_service, get_user_service
from backend.main import app


@pytest.fixture(autouse=True)
def reset_formal_services():
    get_user_service().reset()
    get_relation_service().reset()
    get_care_service().reset_sessions()
    get_device_service().reset()
    yield
    get_user_service().reset()
    get_relation_service().reset()
    get_care_service().reset_sessions()
    get_device_service().reset()


def community_auth_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/mock-login",
        json={"username": "community_admin", "password": "123456"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def family_auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:10", "device_name": "T10-WATCH"},
        headers=community_auth_headers(client),
    )
    accounts = client.get("/api/v1/auth/mock-accounts")
    family_username = next(item["username"] for item in accounts.json() if item["role"] == "family")
    login = client.post(
        "/api/v1/auth/mock-login",
        json={"username": family_username, "password": "123456"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def formal_auth_headers(client: TestClient, username: str, password: str = "123456") -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_register_elder_and_family_then_bind_relation() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Zhang Guilan",
            "phone": "13800138000",
            "password": "123456",
            "age": 78,
            "apartment": "2-301",
        },
        headers=headers,
    )
    assert elder.status_code == 200
    elder_id = elder.json()["id"]

    family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Li Na",
            "phone": "13900139000",
            "password": "123456",
            "relationship": "daughter",
        },
        headers=headers,
    )
    assert family.status_code == 200
    family_id = family.json()["id"]

    relation = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "daughter",
            "is_primary": True,
        },
        headers=headers,
    )
    assert relation.status_code == 200
    assert relation.json()["elder_user_id"] == elder_id
    assert relation.json()["family_user_id"] == family_id


def test_register_user_rejects_duplicate_phone() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    first = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "First Elder",
            "phone": "13800138003",
            "password": "123456",
            "age": 72,
            "apartment": "1-201",
        },
        headers=headers,
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Duplicate Family",
            "phone": "13800138003",
            "password": "123456",
            "relationship": "daughter",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "PHONE_ALREADY_EXISTS"


def test_relation_bind_rejects_duplicate_and_wrong_roles() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Formal Elder",
            "phone": "13800138004",
            "password": "123456",
            "age": 79,
            "apartment": "4-201",
        },
        headers=headers,
    )
    elder_id = elder.json()["id"]
    family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Formal Family",
            "phone": "13900139004",
            "password": "123456",
            "relationship": "son",
        },
        headers=headers,
    )
    family_id = family.json()["id"]

    first = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "son",
            "is_primary": True,
        },
        headers=headers,
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "son",
            "is_primary": False,
        },
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "RELATION_ALREADY_EXISTS"

    wrong_role = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": family_id,
            "family_user_id": elder_id,
            "relation_type": "invalid",
            "is_primary": False,
        },
        headers=headers,
    )
    assert wrong_role.status_code == 400
    assert wrong_role.json()["detail"] == "INVALID_USER_ROLE"


def test_device_register_requires_existing_elder_when_user_id_present() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    missing_user = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:DF",
            "device_name": "T10-WATCH",
            "user_id": "missing-user-id",
        },
        headers=headers,
    )
    assert missing_user.status_code == 404
    assert missing_user.json()["detail"] == "USER_NOT_FOUND"

    missing_lookup = client.get("/api/v1/devices/53:57:08:01:00:DF")
    assert missing_lookup.status_code == 404

    family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Child User",
            "phone": "13900139001",
            "password": "123456",
            "relationship": "son",
        },
        headers=headers,
    )
    family_id = family.json()["id"]

    wrong_role = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:E0",
            "device_name": "T10-WATCH",
            "user_id": family_id,
        },
        headers=headers,
    )
    assert wrong_role.status_code == 400
    assert wrong_role.json()["detail"] == "INVALID_BIND_TARGET_ROLE"

    wrong_role_lookup = client.get("/api/v1/devices/53:57:08:01:00:E0")
    assert wrong_role_lookup.status_code == 404


def test_device_register_rejects_duplicate_mac() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    first = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:E1",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:E1",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "DEVICE_ALREADY_EXISTS"


def test_device_register_without_binding_stays_unbound() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    response = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:E2",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] is None
    assert payload["status"] == "offline"
    assert payload["bind_status"] == "unbound"


def test_bind_unbind_and_rebind_device_flow() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_a = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Bound Elder A",
            "phone": "13800138007",
            "password": "123456",
            "age": 75,
            "apartment": "7-101",
        },
        headers=headers,
    ).json()["id"]
    elder_b = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Bound Elder B",
            "phone": "13800138008",
            "password": "123456",
            "age": 77,
            "apartment": "7-102",
        },
        headers=headers,
    ).json()["id"]

    register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:E3",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert register.status_code == 200

    bind = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:00:E3",
            "target_user_id": elder_a,
            "operator_id": "community-operator",
        },
        headers=headers,
    )
    assert bind.status_code == 200
    assert bind.json()["action_type"] == "bind"
    assert bind.json()["new_user_id"] == elder_a

    device_after_bind = client.get("/api/v1/devices/53:57:08:01:00:E3")
    assert device_after_bind.json()["user_id"] == elder_a
    assert device_after_bind.json()["bind_status"] == "bound"

    rebind = client.post(
        "/api/v1/devices/rebind",
        json={
            "mac_address": "53:57:08:01:00:E3",
            "new_user_id": elder_b,
            "operator_id": "community-operator",
            "reason": "transfer",
        },
        headers=headers,
    )
    assert rebind.status_code == 200
    assert rebind.json()["action_type"] == "rebind"
    assert rebind.json()["old_user_id"] == elder_a
    assert rebind.json()["new_user_id"] == elder_b

    unbind = client.post(
        "/api/v1/devices/unbind",
        json={
            "mac_address": "53:57:08:01:00:E3",
            "operator_id": "community-operator",
            "reason": "maintenance",
        },
        headers=headers,
    )
    assert unbind.status_code == 200
    assert unbind.json()["action_type"] == "unbind"
    assert unbind.json()["old_user_id"] == elder_b
    assert unbind.json()["new_user_id"] is None

    device_after_unbind = client.get("/api/v1/devices/53:57:08:01:00:E3")
    assert device_after_unbind.json()["user_id"] is None
    assert device_after_unbind.json()["bind_status"] == "unbound"

    logs = client.get("/api/v1/devices/53:57:08:01:00:E3/bind-logs")
    assert logs.status_code == 200
    assert [item["action_type"] for item in logs.json()] == ["bind", "rebind", "unbind"]


def test_bind_conflict_and_unbind_guardrails() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_a = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Conflict Elder A",
            "phone": "13800138009",
            "password": "123456",
            "age": 74,
            "apartment": "8-101",
        },
        headers=headers,
    ).json()["id"]
    elder_b = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Conflict Elder B",
            "phone": "13800138010",
            "password": "123456",
            "age": 73,
            "apartment": "8-102",
        },
        headers=headers,
    ).json()["id"]

    client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E4", "device_name": "T10-WATCH"},
        headers=headers,
    )
    first_bind = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "53:57:08:01:00:E4", "target_user_id": elder_a},
        headers=headers,
    )
    assert first_bind.status_code == 200

    conflict_bind = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "53:57:08:01:00:E4", "target_user_id": elder_b},
        headers=headers,
    )
    assert conflict_bind.status_code == 409
    assert conflict_bind.json()["detail"] == "DEVICE_ALREADY_BOUND"

    duplicate_target = client.post(
        "/api/v1/devices/rebind",
        json={"mac_address": "53:57:08:01:00:E4", "new_user_id": elder_a},
        headers=headers,
    )
    assert duplicate_target.status_code == 409
    assert duplicate_target.json()["detail"] == "DEVICE_ALREADY_BOUND_TO_TARGET"

    client.post("/api/v1/devices/unbind", json={"mac_address": "53:57:08:01:00:E4"}, headers=headers)
    second_unbind = client.post("/api/v1/devices/unbind", json={"mac_address": "53:57:08:01:00:E4"}, headers=headers)
    assert second_unbind.status_code == 400
    assert second_unbind.json()["detail"] == "DEVICE_NOT_BOUND"


def test_management_write_operations_require_login_allow_family_and_forbid_elder() -> None:
    client = TestClient(app)

    unauthenticated = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E5", "device_name": "T10-WATCH"},
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"] == "AUTH_REQUIRED"

    family_headers = family_auth_headers(client)
    family_register = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E5", "device_name": "T10-WATCH"},
        headers=family_headers,
    )
    assert family_register.status_code == 200

    managed_elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Family Writable Elder",
            "phone": "13800138124",
            "password": "123456",
            "age": 78,
            "apartment": "11-102",
        },
        headers=community_auth_headers(client),
    )
    assert managed_elder.status_code == 200
    managed_elder_id = managed_elder.json()["id"]

    unbound_device = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E6", "device_name": "THERMO-PAD"},
        headers=community_auth_headers(client),
    )
    assert unbound_device.status_code == 200

    family_bind = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "53:57:08:01:00:E6", "target_user_id": managed_elder_id},
        headers=family_headers,
    )
    assert family_bind.status_code == 200

    elder = client.post(
        "/api/v1/auth/register/elder",
        json={
            "name": "Formal Elder Writer",
            "phone": "13800138123",
            "password": "123456",
            "age": 79,
            "apartment": "11-101",
        },
    )
    assert elder.status_code == 200
    elder_headers = formal_auth_headers(client, "13800138123")
    elder_register = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E8", "device_name": "T10-WATCH"},
        headers=elder_headers,
    )
    assert elder_register.status_code == 403
    assert elder_register.json()["detail"] == "FORBIDDEN"

    community_headers = community_auth_headers(client)
    community_register = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Writer Elder",
            "phone": "13800138088",
            "password": "123456",
            "age": 79,
            "apartment": "9-101",
        },
        headers=community_headers,
    )
    assert community_register.status_code == 200


def test_same_elder_can_have_multiple_models_but_not_duplicate_model_bindings() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_a = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Cardinality Elder A",
            "phone": "13800138131",
            "password": "123456",
            "age": 79,
            "apartment": "13-101",
        },
        headers=headers,
    ).json()["id"]
    elder_b = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Cardinality Elder B",
            "phone": "13800138132",
            "password": "123456",
            "age": 78,
            "apartment": "13-102",
        },
        headers=headers,
    ).json()["id"]

    first_same_model = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F1",
            "device_name": "T10-WATCH",
            "user_id": elder_a,
        },
        headers=headers,
    )
    assert first_same_model.status_code == 200

    duplicate_model_register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F2",
            "device_name": "T10-WATCH",
            "user_id": elder_a,
        },
        headers=headers,
    )
    assert duplicate_model_register.status_code == 409
    assert duplicate_model_register.json()["detail"] == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"

    second_same_model_unbound = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F3",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert second_same_model_unbound.status_code == 200

    duplicate_model_bind = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:00:F3",
            "target_user_id": elder_a,
        },
        headers=headers,
    )
    assert duplicate_model_bind.status_code == 409
    assert duplicate_model_bind.json()["detail"] == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"

    different_model_register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F4",
            "device_name": "T20-BAND",
            "user_id": elder_a,
        },
        headers=headers,
    )
    assert different_model_register.status_code == 200

    bind_other_elder = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:00:F3",
            "target_user_id": elder_b,
        },
        headers=headers,
    )
    assert bind_other_elder.status_code == 200


def test_care_directory_exposes_all_device_macs_for_multi_device_elder() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Directory Multi Device Elder",
            "phone": "13800138141",
            "password": "123456",
            "age": 80,
            "apartment": "14-101",
        },
        headers=headers,
    ).json()["id"]

    first = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F5",
            "device_name": "T10-WATCH",
            "user_id": elder,
        },
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F6",
            "device_name": "T20-BAND",
            "user_id": elder,
        },
        headers=headers,
    )
    assert second.status_code == 200

    directory = client.get("/api/v1/care/directory")
    assert directory.status_code == 200
    elder_payload = next(item for item in directory.json()["elders"] if item["id"] == elder)
    assert elder_payload["device_mac"] == "53:57:08:01:00:F5"
    assert elder_payload["device_macs"] == ["53:57:08:01:00:F5", "53:57:08:01:00:F6"]


def test_device_register_rejects_invalid_mac_format_and_prefix() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    invalid_format = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "not-a-mac", "device_name": "T10-WATCH"},
        headers=headers,
    )
    assert invalid_format.status_code == 422
    assert "INVALID_MAC_ADDRESS" in invalid_format.json()["detail"][0]["msg"]

    invalid_prefix = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "54:10:26:01:00:E6", "device_name": "T10-WATCH"},
        headers=headers,
    )
    assert invalid_prefix.status_code == 422
    assert "INVALID_MAC_PREFIX" in invalid_prefix.json()["detail"][0]["msg"]


@pytest.mark.parametrize(
    ("path", "payload", "expected_error"),
    [
        ("/api/v1/devices/bind", {"mac_address": "not-a-mac", "target_user_id": "elder-x"}, "INVALID_MAC_ADDRESS"),
        ("/api/v1/devices/unbind", {"mac_address": "not-a-mac"}, "INVALID_MAC_ADDRESS"),
        ("/api/v1/devices/rebind", {"mac_address": "not-a-mac", "new_user_id": "elder-x"}, "INVALID_MAC_ADDRESS"),
        ("/api/v1/devices/bind", {"mac_address": "54:10:26:01:00:E6", "target_user_id": "elder-x"}, "INVALID_MAC_PREFIX"),
        ("/api/v1/devices/unbind", {"mac_address": "54:10:26:01:00:E6"}, "INVALID_MAC_PREFIX"),
        ("/api/v1/devices/rebind", {"mac_address": "54:10:26:01:00:E6", "new_user_id": "elder-x"}, "INVALID_MAC_PREFIX"),
    ],
)
def test_device_write_operations_should_reject_invalid_mac_format_and_prefix(
    path: str,
    payload: dict[str, str],
    expected_error: str,
) -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    response = client.post(path, json=payload, headers=headers)

    assert response.status_code == 422
    assert expected_error in response.json()["detail"][0]["msg"]


def test_care_directory_prefers_formal_registered_data() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Formal Elder",
            "phone": "13800138002",
            "password": "123456",
            "age": 81,
            "apartment": "3-502",
        },
        headers=headers,
    )
    elder_id = elder.json()["id"]
    family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Formal Family",
            "phone": "13900139002",
            "password": "123456",
            "relationship": "daughter",
        },
        headers=headers,
    )
    family_id = family.json()["id"]
    client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "daughter",
            "is_primary": True,
        },
        headers=headers,
    )

    directory = client.get("/api/v1/care/directory")
    assert directory.status_code == 200
    payload = directory.json()
    assert [elder_item["id"] for elder_item in payload["elders"]] == [elder_id]
    assert [family_item["id"] for family_item in payload["families"]] == [family_id]
    assert payload["elders"][0]["family_ids"] == [family_id]


def test_family_directory_is_scoped_for_formal_data() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_a = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Elder A",
            "phone": "13800138005",
            "password": "123456",
            "age": 76,
            "apartment": "5-101",
        },
        headers=headers,
    ).json()["id"]
    elder_b = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Elder B",
            "phone": "13800138006",
            "password": "123456",
            "age": 82,
            "apartment": "5-102",
        },
        headers=headers,
    ).json()["id"]
    family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Scoped Family",
            "phone": "13900139005",
            "password": "123456",
            "relationship": "daughter",
        },
        headers=headers,
    ).json()["id"]
    other_family = client.post(
        "/api/v1/users/families/register",
        json={
            "name": "Other Family",
            "phone": "13900139006",
            "password": "123456",
            "relationship": "son",
        },
        headers=headers,
    ).json()["id"]

    client.post(
        "/api/v1/relations/family-bind",
        json={"elder_user_id": elder_a, "family_user_id": family, "relation_type": "daughter", "is_primary": True},
        headers=headers,
    )
    client.post(
        "/api/v1/relations/family-bind",
        json={"elder_user_id": elder_b, "family_user_id": other_family, "relation_type": "son", "is_primary": True},
        headers=headers,
    )

    scoped = client.get(f"/api/v1/care/directory/family/{family}")
    assert scoped.status_code == 200
    payload = scoped.json()
    assert [item["id"] for item in payload["families"]] == [family]
    assert [item["id"] for item in payload["elders"]] == [elder_a]


def test_delete_device_requires_reregistration_before_binding_again() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Delete Flow Elder",
            "phone": "13800138111",
            "password": "123456",
            "age": 80,
            "apartment": "10-101",
        },
        headers=headers,
    ).json()["id"]

    register = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E7", "device_name": "T10-WATCH", "user_id": elder},
        headers=headers,
    )
    assert register.status_code == 200
    assert register.json()["bind_status"] == "bound"

    delete_response = client.delete("/api/v1/devices/53:57:08:01:00:E7", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["mac_address"] == "53:57:08:01:00:E7"

    missing = client.get("/api/v1/devices/53:57:08:01:00:E7")
    assert missing.status_code == 404

    bind_after_delete = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "53:57:08:01:00:E7", "target_user_id": elder},
        headers=headers,
    )
    assert bind_after_delete.status_code == 404
    assert bind_after_delete.json()["detail"] == "DEVICE_NOT_FOUND"

    re_register = client.post(
        "/api/v1/devices/register",
        json={"mac_address": "53:57:08:01:00:E7", "device_name": "T10-WATCH"},
        headers=headers,
    )
    assert re_register.status_code == 200

    rebind = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "53:57:08:01:00:E7", "target_user_id": elder},
        headers=headers,
    )
    assert rebind.status_code == 200


def test_device_write_requests_reject_invalid_mac_consistently() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    invalid_bind = client.post(
        "/api/v1/devices/bind",
        json={"mac_address": "bad-mac", "target_user_id": "elder-id"},
        headers=headers,
    )
    assert invalid_bind.status_code == 422
    assert "INVALID_MAC_ADDRESS" in invalid_bind.json()["detail"][0]["msg"]

    invalid_unbind = client.post(
        "/api/v1/devices/unbind",
        json={"mac_address": "bad-mac"},
        headers=headers,
    )
    assert invalid_unbind.status_code == 422
    assert "INVALID_MAC_ADDRESS" in invalid_unbind.json()["detail"][0]["msg"]

    invalid_rebind = client.post(
        "/api/v1/devices/rebind",
        json={"mac_address": "bad-mac", "new_user_id": "elder-id"},
        headers=headers,
    )
    assert invalid_rebind.status_code == 422
    assert "INVALID_MAC_ADDRESS" in invalid_rebind.json()["detail"][0]["msg"]


def test_register_with_binding_keeps_operator_audit_context() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Audit Elder",
            "phone": "13800138118",
            "password": "123456",
            "age": 80,
            "apartment": "12-101",
        },
        headers=headers,
    ).json()["id"]

    register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F8",
            "device_name": "T10-WATCH",
            "user_id": elder,
        },
        headers=headers,
    )
    assert register.status_code == 200

    logs = client.get("/api/v1/devices/53:57:08:01:00:F8/bind-logs")
    assert logs.status_code == 200
    payload = logs.json()
    assert len(payload) == 1
    assert payload[0]["action_type"] == "bind"
    assert payload[0]["operator_id"] == "user-community-admin"


def test_elder_can_have_multiple_devices_but_only_one_per_device_model() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_id = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Multi Device Elder",
            "phone": "13800138119",
            "password": "123456",
            "age": 79,
            "apartment": "12-102",
        },
        headers=headers,
    ).json()["id"]

    first = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F9",
            "device_name": "T10-WATCH",
            "user_id": elder_id,
        },
        headers=headers,
    )
    assert first.status_code == 200

    second_model = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:FA",
            "device_name": "THERMO-PAD",
            "user_id": elder_id,
        },
        headers=headers,
    )
    assert second_model.status_code == 200

    duplicate_model = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:FB",
            "device_name": "t10-watch",
            "user_id": elder_id,
        },
        headers=headers,
    )
    assert duplicate_model.status_code == 409
    assert duplicate_model.json()["detail"] == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"

    directory = client.get("/api/v1/care/directory")
    assert directory.status_code == 200
    elder_payload = directory.json()["elders"][0]
    assert elder_payload["device_mac"] == "53:57:08:01:00:F9"
    assert elder_payload["device_macs"] == ["53:57:08:01:00:F9", "53:57:08:01:00:FA"]


def test_bind_and_rebind_reject_same_model_duplicates_for_one_elder() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)

    elder_id = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Same Model Elder",
            "phone": "13800138120",
            "password": "123456",
            "age": 81,
            "apartment": "12-103",
        },
        headers=headers,
    ).json()["id"]
    other_elder_id = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Other Elder",
            "phone": "13800138121",
            "password": "123456",
            "age": 82,
            "apartment": "12-104",
        },
        headers=headers,
    ).json()["id"]

    client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:FC",
            "device_name": "T10-WATCH",
            "user_id": elder_id,
        },
        headers=headers,
    )
    free_device = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:FD",
            "device_name": "T10-WATCH",
        },
        headers=headers,
    )
    assert free_device.status_code == 200

    bind_conflict = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:00:FD",
            "target_user_id": elder_id,
        },
        headers=headers,
    )
    assert bind_conflict.status_code == 409
    assert bind_conflict.json()["detail"] == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"

    first_other = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:FE",
            "device_name": "T10-WATCH",
            "user_id": other_elder_id,
        },
        headers=headers,
    )
    assert first_other.status_code == 200

    rebind_conflict = client.post(
        "/api/v1/devices/rebind",
        json={
            "mac_address": "53:57:08:01:00:FC",
            "new_user_id": other_elder_id,
        },
        headers=headers,
    )
    assert rebind_conflict.status_code == 409
    assert rebind_conflict.json()["detail"] == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"


def test_device_read_endpoints_remain_public() -> None:
    client = TestClient(app)
    community_headers = community_auth_headers(client)

    register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:01:20",
            "device_name": "T10-WATCH",
        },
        headers=community_headers,
    )
    assert register.status_code == 200

    device_list = client.get("/api/v1/devices")
    assert device_list.status_code == 200
    assert any(item["mac_address"] == "53:57:08:01:01:20" for item in device_list.json())

    device_detail = client.get("/api/v1/devices/53:57:08:01:01:20")
    assert device_detail.status_code == 200
    assert device_detail.json()["mac_address"] == "53:57:08:01:01:20"

    bind_logs = client.get("/api/v1/devices/53:57:08:01:01:20/bind-logs")
    assert bind_logs.status_code == 200
    assert bind_logs.json() == []


def test_family_user_can_bind_device_via_api_capability() -> None:
    client = TestClient(app)
    community_headers = community_auth_headers(client)

    managed_elder_id = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Policy Elder",
            "phone": "13800138151",
            "password": "123456",
            "age": 80,
            "apartment": "15-101",
        },
        headers=community_headers,
    ).json()["id"]

    register = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:01:21",
            "device_name": "T10-WATCH",
        },
        headers=community_headers,
    )
    assert register.status_code == 200

    family_headers = family_auth_headers(client)
    family_bind = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:01:21",
            "target_user_id": managed_elder_id,
        },
        headers=family_headers,
    )

    assert family_bind.status_code == 200
    assert family_bind.json()["action_type"] == "bind"
    assert family_bind.json()["new_user_id"] == managed_elder_id


def test_formal_family_user_can_bind_device_after_registration_while_elder_cannot() -> None:
    client = TestClient(app)
    community_headers = community_auth_headers(client)

    managed_elder_id = client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Formal Policy Elder",
            "phone": "13800138152",
            "password": "123456",
            "age": 79,
            "apartment": "15-102",
        },
        headers=community_headers,
    ).json()["id"]

    family_registration = client.post(
        "/api/v1/auth/register/family",
        json={
            "name": "Formal Family Binder",
            "phone": "13900139152",
            "password": "123456",
            "relationship": "daughter",
            "login_username": "family_bind_152",
        },
    )
    assert family_registration.status_code == 200
    family_headers = formal_auth_headers(client, "family_bind_152")

    first_device = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:01:22",
            "device_name": "T10-WATCH",
        },
        headers=community_headers,
    )
    assert first_device.status_code == 200

    family_bind = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:01:22",
            "target_user_id": managed_elder_id,
        },
        headers=family_headers,
    )
    assert family_bind.status_code == 200
    assert family_bind.json()["action_type"] == "bind"

    elder_registration = client.post(
        "/api/v1/auth/register/elder",
        json={
            "name": "Formal Elder Binder",
            "phone": "13800138153",
            "password": "123456",
            "age": 78,
            "apartment": "15-103",
        },
    )
    assert elder_registration.status_code == 200
    elder_headers = formal_auth_headers(client, "13800138153")

    second_device = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:01:23",
            "device_name": "T10-WATCH",
        },
        headers=community_headers,
    )
    assert second_device.status_code == 200

    elder_bind = client.post(
        "/api/v1/devices/bind",
        json={
            "mac_address": "53:57:08:01:01:23",
            "target_user_id": managed_elder_id,
        },
        headers=elder_headers,
    )
    assert elder_bind.status_code == 403
    assert elder_bind.json()["detail"] == "FORBIDDEN"
