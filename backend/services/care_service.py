from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.config import Settings
from backend.models.auth_model import AuthAccountPreview, LoginResponse, SessionUser
from backend.models.care_model import CareDirectory, CommunityProfile, ElderProfile, FamilyProfile
from backend.models.device_model import DeviceRecord
from backend.models.user_model import UserRole
from backend.services.device_service import DeviceService
from backend.services.relation_service import RelationService
from backend.services.user_service import UserService


ELDER_NAME_POOL = [
    "Zhang Guihua",
    "Li Xiuying",
    "Wang Shulan",
    "Chen Yulan",
    "Zhou Lanying",
    "Wu Xiuzhen",
    "Liu Yumei",
    "Xu Guiying",
    "Sun Yulan",
    "Ma Xiulan",
]

FAMILY_NAME_POOL = [
    "Li Na",
    "Zhang Min",
    "Wang Lei",
    "Chen Fang",
    "Zhou Qiang",
    "Wu Jing",
]

RELATIONSHIP_POOL = ["daughter", "son", "spouse", "granddaughter", "grandson", "relative"]


def _pick_from_pool(pool: list[str], index: int, fallback_prefix: str) -> str:
    if not pool:
        return f"{fallback_prefix}{index + 1}"
    return pool[index % len(pool)]


def _build_phone(index: int) -> str:
    return f"1380000{str(1200 + index)[-4:]}"


@dataclass(slots=True)
class AccountRecord:
    username: str
    password: str
    user: SessionUser


class CareService:
    """Provides directory aggregation and keeps demo auth isolated from formal registration."""

    def __init__(
        self,
        device_service: DeviceService,
        user_service: UserService,
        relation_service: RelationService,
        settings: Settings,
    ) -> None:
        self._device_service = device_service
        self._user_service = user_service
        self._relation_service = relation_service
        self._settings = settings
        self._session_store: dict[str, SessionUser] = {}
        self._session_expiry: dict[str, datetime] = {}
        self._session_ttl = timedelta(hours=12)

    def get_directory(self) -> CareDirectory:
        formal_directory = self._build_formal_directory()
        if formal_directory is not None:
            return formal_directory
        return self._build_demo_directory(self._device_service.list_devices())

    def get_family_directory(self, family_id: str) -> CareDirectory:
        directory = self.get_directory()
        family = next((item for item in directory.families if item.id == family_id), None)
        if not family:
            return CareDirectory(community=directory.community, elders=[], families=[])
        elder_set = set(family.elder_ids)
        elders = [elder for elder in directory.elders if elder.id in elder_set]
        return CareDirectory(community=directory.community, elders=elders, families=[family])

    def list_auth_accounts(self) -> list[AuthAccountPreview]:
        records = self._build_demo_accounts()
        return [
            AuthAccountPreview(
                username=record.username,
                display_name=record.user.name,
                role=record.user.role,
                family_id=record.user.family_id,
                community_id=record.user.community_id,
            )
            for record in records
        ]

    def login(self, username: str, password: str) -> LoginResponse | None:
        formal = self.login_formal(username, password)
        if formal is not None:
            return formal
        return self.login_demo(username, password)

    def login_demo(self, username: str, password: str) -> LoginResponse | None:
        normalized_username = username.strip().lower()
        record = next((item for item in self._build_demo_accounts() if item.username == normalized_username), None)
        if not record or record.password != password:
            return None
        return self._open_session(record.user)

    def login_formal(self, username: str, password: str) -> LoginResponse | None:
        user = self._user_service.authenticate_user(username, password)
        if user is None:
            return None
        session_user = self._build_formal_session_user(user)
        if session_user is None:
            return None
        return self._open_session(session_user)

    def _open_session(self, user: SessionUser) -> LoginResponse:
        token = str(uuid4())
        self._session_store[token] = user
        self._session_expiry[token] = datetime.now(timezone.utc) + self._session_ttl
        return LoginResponse(token=token, user=user, expires_at=self._session_expiry[token])

    def resolve_session(self, token: str) -> SessionUser | None:
        normalized = token.strip()
        if not normalized:
            return None
        expires_at = self._session_expiry.get(normalized)
        if expires_at is None:
            return None
        if expires_at < datetime.now(timezone.utc):
            self._session_expiry.pop(normalized, None)
            self._session_store.pop(normalized, None)
            return None
        return self._session_store.get(normalized)

    def reset_sessions(self) -> None:
        self._session_store.clear()
        self._session_expiry.clear()

    def _build_formal_directory(self) -> CareDirectory | None:
        if not self._user_service.has_formal_users():
            return None
        community = self._community_profile()
        devices_by_user: dict[str, list[DeviceRecord]] = {}
        for device in self._device_service.list_devices():
            if device.user_id:
                devices_by_user.setdefault(device.user_id, []).append(device)

        elders: list[ElderProfile] = []
        for user in self._user_service.list_users(role=UserRole.ELDER):
            profile = self._user_service.get_elder_profile(user.id)
            if profile is None:
                continue
            relations = self._relation_service.list_relations_by_elder(user.id)
            elder_devices = sorted(devices_by_user.get(user.id, []), key=lambda item: item.created_at)
            elder_device_macs = [device.mac_address for device in elder_devices]
            elders.append(
                ElderProfile(
                    id=user.id,
                    name=user.name,
                    age=profile.age,
                    apartment=profile.apartment,
                    community_id=profile.community_id,
                    device_mac=elder_device_macs[0] if elder_device_macs else "",
                    device_macs=elder_device_macs,
                    family_ids=[relation.family_user_id for relation in relations if relation.status == "active"],
                )
            )

        families: list[FamilyProfile] = []
        for user in self._user_service.list_users(role=UserRole.FAMILY):
            profile = self._user_service.get_family_profile(user.id)
            if profile is None:
                continue
            relations = self._relation_service.list_relations_by_family(user.id)
            families.append(
                FamilyProfile(
                    id=user.id,
                    name=user.name,
                    relationship=profile.relationship,
                    phone=user.phone,
                    community_id=profile.community_id,
                    elder_ids=[relation.elder_user_id for relation in relations if relation.status == "active"],
                    login_username=profile.login_username,
                )
            )

        return CareDirectory(community=community, elders=elders, families=families)

    def _build_demo_accounts(self) -> list[AccountRecord]:
        directory = self._build_demo_directory(self._device_service.list_devices())
        community_user = SessionUser(
            id="user-community-admin",
            username="community_admin",
            name=f"{directory.community.name} Admin",
            role=UserRole.COMMUNITY,
            community_id=directory.community.id,
            family_id=None,
        )
        records = [AccountRecord(username="community_admin", password="123456", user=community_user)]
        for family in directory.families:
            records.append(
                AccountRecord(
                    username=family.login_username.lower(),
                    password="123456",
                    user=SessionUser(
                        id=f"user-{family.id}",
                        username=family.login_username.lower(),
                        name=family.name,
                        role=UserRole.FAMILY,
                        community_id=directory.community.id,
                        family_id=family.id,
                    ),
                )
            )
        return records

    def _build_formal_session_user(self, user) -> SessionUser | None:
        if user.role == UserRole.ELDER:
            profile = self._user_service.get_elder_profile(user.id)
            if profile is None:
                return None
            return SessionUser(
                id=user.id,
                username=user.phone,
                name=user.name,
                role=user.role,
                community_id=profile.community_id,
                family_id=None,
            )

        if user.role == UserRole.FAMILY:
            profile = self._user_service.get_family_profile(user.id)
            if profile is None:
                return None
            return SessionUser(
                id=user.id,
                username=profile.login_username,
                name=user.name,
                role=user.role,
                community_id=profile.community_id,
                family_id=user.id,
            )

        if user.role == UserRole.COMMUNITY:
            profile = self._user_service.get_community_profile(user.id)
            if profile is None:
                return None
            return SessionUser(
                id=user.id,
                username=profile.login_username,
                name=user.name,
                role=user.role,
                community_id=profile.community_id,
                family_id=None,
            )

        return None

    def _build_demo_directory(self, devices: list[DeviceRecord]) -> CareDirectory:
        sorted_devices = sorted(devices, key=lambda item: item.mac_address)
        community = self._community_profile()
        elders: list[ElderProfile] = []
        family_map: dict[str, FamilyProfile] = {}

        for index, device in enumerate(sorted_devices):
            family_index = index // 2
            family_id = f"family-{family_index + 1}"
            if family_id not in family_map:
                family_map[family_id] = FamilyProfile(
                    id=family_id,
                    name=_pick_from_pool(FAMILY_NAME_POOL, family_index, "Family"),
                    relationship=_pick_from_pool(RELATIONSHIP_POOL, family_index, "relative"),
                    phone=_build_phone(family_index),
                    community_id=community.id,
                    elder_ids=[],
                    login_username=f"family{family_index + 1:02d}",
                )
            elder = ElderProfile(
                id=f"elder-{index + 1}",
                name=_pick_from_pool(ELDER_NAME_POOL, index, "Elder"),
                age=67 + (index % 17),
                apartment=f"{index // 3 + 1}-{100 + (index % 12)}",
                community_id=community.id,
                device_mac=device.mac_address,
                device_macs=[device.mac_address],
                family_ids=[family_id],
            )
            elders.append(elder)
            family_map[family_id].elder_ids.append(elder.id)

        return CareDirectory(community=community, elders=elders, families=list(family_map.values()))

    @staticmethod
    def _community_profile() -> CommunityProfile:
        return CommunityProfile(
            id="community-haitang",
            name="Haitang Community",
            address="68 Haitang Road",
            manager="Community Manager",
            hotline="400-810-6868",
        )
