import { computed, ref } from "vue";
import { ApiError, api, type SessionUser } from "../api/client";
import {
  DEFAULT_DEMO_PASSWORD,
  LAST_LOGIN_USERNAME_KEY,
  resolveInitialLoginUsername,
} from "../constants/demoAuth";

export const SESSION_KEY = "ai_health_demo_session_token";

const LOGIN_TIMEOUT_MS = 6000;
const LOGIN_RETRY_DELAY_MS = 450;
const SESSION_RESTORE_TIMEOUT_MS = 3000;
const RETRYABLE_AUTH_STATUSES = new Set([408, 429, 500, 502, 503, 504]);

export function getStoredSessionToken() {
  const token = localStorage.getItem(SESSION_KEY)?.trim() ?? "";
  if (!token || token === "null" || token === "undefined") {
    return "";
  }
  return token;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatAuthError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function isRetryableAuthError(error: unknown) {
  return error instanceof ApiError && RETRYABLE_AUTH_STATUSES.has(error.status);
}

export function useSessionAuth() {
  const sessionUser = ref<SessionUser | null>(null);
  const loginUsername = ref(resolveInitialLoginUsername());
  const loginPassword = ref(DEFAULT_DEMO_PASSWORD);
  const authLoading = ref(false);
  const authError = ref("");

  const isLoggedIn = computed(() => sessionUser.value !== null);

  async function loginOnce() {
    return api.login(
      {
        username: loginUsername.value.trim(),
        password: loginPassword.value,
      },
      { timeoutMs: LOGIN_TIMEOUT_MS },
    );
  }

  async function login() {
    authError.value = "";

    if (!loginUsername.value.trim()) {
      authError.value = "请输入账号、登录名或手机号。";
      return null;
    }

    if (!loginPassword.value.trim()) {
      authError.value = "请输入密码。";
      return null;
    }

    authLoading.value = true;
    try {
      let lastError: unknown = null;

      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          const result = await loginOnce();
          sessionUser.value = result.user;
          localStorage.setItem(SESSION_KEY, result.token);
          localStorage.setItem(LAST_LOGIN_USERNAME_KEY, result.user.username || loginUsername.value.trim());
          return result.user;
        } catch (error) {
          lastError = error;
          if (attempt === 0 && isRetryableAuthError(error)) {
            await sleep(LOGIN_RETRY_DELAY_MS);
            continue;
          }
          break;
        }
      }

      authError.value = formatAuthError(lastError, "登录失败，请检查账号、密码或后端服务状态。");
      return null;
    } finally {
      authLoading.value = false;
    }
  }

  async function restoreSession() {
    const token = getStoredSessionToken();
    if (!token) return;

    const user = await api.me(token, { timeoutMs: SESSION_RESTORE_TIMEOUT_MS }).catch(() => null);
    if (!user) {
      localStorage.removeItem(SESSION_KEY);
      return;
    }

    sessionUser.value = user;
  }

  function logoutSession() {
    localStorage.removeItem(SESSION_KEY);
  }

  return {
    authError,
    authLoading,
    isLoggedIn,
    login,
    loginPassword,
    loginUsername,
    logoutSession,
    restoreSession,
    sessionUser,
  };
}
