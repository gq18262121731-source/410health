import type { AuthAccountPreview } from "../api/client";

export const LAST_LOGIN_USERNAME_KEY = "ai_health_demo_last_login_username";
export const DEFAULT_DEMO_PASSWORD = "123456";
export const DEFAULT_DEMO_USERNAME = "community_admin";

export const LOCAL_DEMO_ACCOUNTS: AuthAccountPreview[] = [
  {
    username: "community_admin",
    display_name: "社区管理员",
    role: "community",
    family_id: null,
    community_id: "community-haitang",
    default_password: DEFAULT_DEMO_PASSWORD,
  },
  {
    username: "family01",
    display_name: "家属 01",
    role: "family",
    family_id: "family01",
    community_id: "community-haitang",
    default_password: DEFAULT_DEMO_PASSWORD,
  },
  {
    username: "elder01_02",
    display_name: "老人 01-02",
    role: "elder",
    family_id: "family01",
    community_id: "community-haitang",
    default_password: DEFAULT_DEMO_PASSWORD,
  },
];

export function getStoredLastLoginUsername() {
  return localStorage.getItem(LAST_LOGIN_USERNAME_KEY)?.trim() ?? "";
}

export function resolveInitialLoginUsername() {
  return getStoredLastLoginUsername() || DEFAULT_DEMO_USERNAME;
}
