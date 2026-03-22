import pytest
from fastapi.testclient import TestClient

from backend.dependencies import (
    get_care_service,
    get_data_generator,
    get_device_service,
    get_relation_service,
    get_user_service,
)
from backend.main import app


@pytest.fixture(autouse=True)
def reset_formal_services():
    get_user_service().reset()
    get_relation_service().reset()
    get_care_service().reset_sessions()
    get_device_service().reset()
    if not get_device_service().list_devices():
        get_device_service().seed_devices(get_data_generator().build_devices())
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


def formal_login_headers(client: TestClient, username: str, password: str = "123456") -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_care_directory_contains_community_elders_and_families() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/care/directory")
    assert response.status_code == 200
    payload = response.json()
    assert payload["community"]["id"]
    assert payload["elders"]
    assert payload["families"]


def test_family_directory_is_scoped() -> None:
    client = TestClient(app)
    full = client.get("/api/v1/care/directory").json()
    first_family_id = full["families"][0]["id"]
    family_directory = client.get(f"/api/v1/care/directory/family/{first_family_id}")
    assert family_directory.status_code == 200
    payload = family_directory.json()
    assert len(payload["families"]) == 1
    assert payload["families"][0]["id"] == first_family_id
    scoped_elder_ids = set(payload["families"][0]["elder_ids"])
    assert scoped_elder_ids == {elder["id"] for elder in payload["elders"]}


def test_care_directory_falls_back_to_demo_without_formal_users() -> None:
    client = TestClient(app)
    payload = client.get("/api/v1/care/directory").json()
    assert payload["elders"][0]["id"].startswith("elder-")
    assert payload["families"][0]["id"].startswith("family-")


def test_mock_login_and_me_flow() -> None:
    client = TestClient(app)
    accounts = client.get("/api/v1/auth/mock-accounts")
    assert accounts.status_code == 200
    assert accounts.json()
    username = accounts.json()[0]["username"]

    login = client.post(
        "/api/v1/auth/mock-login",
        json={"username": username, "password": "123456"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == username


def test_public_registration_and_formal_login_support_community_staff() -> None:
    client = TestClient(app)

    registration = client.post(
        "/api/v1/auth/register/community-staff",
        json={
            "name": "Community Staff One",
            "phone": "13700137001",
            "password": "123456",
            "login_username": "community_worker_01",
            "community_id": "community-haitang",
        },
    )
    assert registration.status_code == 200
    assert registration.json()["role"] == "community"

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "community_worker_01", "password": "123456"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "community"
    assert me.json()["username"] == "community_worker_01"


def test_public_registration_rejects_duplicate_login_username() -> None:
    client = TestClient(app)

    first = client.post(
        "/api/v1/auth/register/community-staff",
        json={
            "name": "Community Staff A",
            "phone": "13700137011",
            "password": "123456",
            "login_username": "community_dup",
        },
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/api/v1/auth/register/family",
        json={
            "name": "Family User",
            "phone": "13700137012",
            "password": "123456",
            "relationship": "daughter",
            "login_username": "community_dup",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "LOGIN_USERNAME_ALREADY_EXISTS"


def test_access_profile_gates_bound_and_unbound_user_features() -> None:
    client = TestClient(app)

    elder = client.post(
        "/api/v1/auth/register/elder",
        json={
            "name": "Formal Elder",
            "phone": "13700137002",
            "password": "123456",
            "age": 76,
            "apartment": "2-301",
        },
    )
    assert elder.status_code == 200
    elder_id = elder.json()["id"]

    family = client.post(
        "/api/v1/auth/register/family",
        json={
            "name": "Formal Family",
            "phone": "13700137003",
            "password": "123456",
            "relationship": "daughter",
            "login_username": "formal_family01",
        },
    )
    assert family.status_code == 200
    family_id = family.json()["id"]

    elder_headers = formal_login_headers(client, "13700137002")
    elder_access = client.get("/api/v1/care/access-profile/me", headers=elder_headers)
    assert elder_access.status_code == 200
    assert elder_access.json()["binding_state"] == "unbound"
    assert elder_access.json()["capabilities"]["basic_advice"] is True
    assert elder_access.json()["capabilities"]["device_metrics"] is False

    family_headers = formal_login_headers(client, "formal_family01")
    family_access = client.get("/api/v1/care/access-profile/me", headers=family_headers)
    assert family_access.status_code == 200
    assert family_access.json()["binding_state"] == "unbound"
    assert family_access.json()["capabilities"]["health_report"] is False

    operator_headers = community_auth_headers(client)
    relation = client.post(
        "/api/v1/relations/family-bind",
        json={
            "elder_user_id": elder_id,
            "family_user_id": family_id,
            "relation_type": "daughter",
            "is_primary": True,
        },
        headers=operator_headers,
    )
    assert relation.status_code == 200
    register_device = client.post(
        "/api/v1/devices/register",
        json={
            "mac_address": "53:57:08:01:00:F1",
            "device_name": "T10-WATCH",
            "user_id": elder_id,
        },
        headers=operator_headers,
    )
    assert register_device.status_code == 200

    elder_bound = client.get("/api/v1/care/access-profile/me", headers=elder_headers)
    assert elder_bound.status_code == 200
    elder_bound_payload = elder_bound.json()
    assert elder_bound_payload["binding_state"] == "bound"
    assert elder_bound_payload["capabilities"]["device_metrics"] is True
    assert elder_bound_payload["capabilities"]["health_evaluation"] is True
    assert elder_bound_payload["bound_device_macs"] == ["53:57:08:01:00:F1"]
    assert elder_bound_payload["health_evaluations"][0]["device_mac"] == "53:57:08:01:00:F1"

    family_bound = client.get("/api/v1/care/access-profile/me", headers=family_headers)
    assert family_bound.status_code == 200
    family_bound_payload = family_bound.json()
    assert family_bound_payload["binding_state"] == "bound"
    assert family_bound_payload["capabilities"]["health_report"] is True
    assert family_bound_payload["health_evaluations"][0]["device_mac"] == "53:57:08:01:00:F1"
    assert family_bound_payload["related_elder_ids"] == [elder_id]
    assert family_bound_payload["bound_device_macs"] == ["53:57:08:01:00:F1"]

    community_formal = client.post(
        "/api/v1/auth/register/community-staff",
        json={
            "name": "Community Viewer",
            "phone": "13700137004",
            "password": "123456",
            "login_username": "community_viewer",
        },
    )
    assert community_formal.status_code == 200
    community_headers = formal_login_headers(client, "community_viewer")
    community_access = client.get("/api/v1/care/access-profile/me", headers=community_headers)
    assert community_access.status_code == 200
    assert community_access.json()["binding_state"] == "not_applicable"


def test_mock_accounts_still_available_after_formal_users_exist() -> None:
    client = TestClient(app)
    headers = community_auth_headers(client)
    client.post(
        "/api/v1/users/elders/register",
        json={
            "name": "Formal Elder",
            "phone": "13800138999",
            "password": "123456",
            "age": 80,
            "apartment": "6-302",
        },
        headers=headers,
    )

    accounts = client.get("/api/v1/auth/mock-accounts")
    assert accounts.status_code == 200
    payload = accounts.json()
    assert payload
    assert any(account["username"] == "community_admin" for account in payload)
