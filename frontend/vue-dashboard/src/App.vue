<script setup lang="ts">
import { onMounted, onUnmounted, watch } from "vue";
import AppShell from "./components/layout/AppShell.vue";
import { useHashRouting } from "./composables/useHashRouting";
import { useSessionAuth } from "./composables/useSessionAuth";
import AccessDeniedPage from "./views/AccessDeniedPage.vue";
import CommunityPage from "./views/CommunityPage.vue";
import DebugPage from "./views/DebugPage.vue";
import FamilyPage from "./views/FamilyPage.vue";
import LoginPage from "./views/LoginPage.vue";
import MemberDevicePage from "./views/MemberDevicePage.vue";

const {
  authError,
  authLoading,
  isLoggedIn,
  login,
  loginPassword,
  loginUsername,
  logoutSession,
  restoreSession,
  sessionUser,
} = useSessionAuth();

const {
  activePage,
  allowedPages,
  canAccessDebug,
  disposeHashRouting,
  initHashRouting,
  resetToDefaultPage,
  routeTo,
} = useHashRouting(sessionUser);

async function submitLogin() {
  const user = await login();
  if (!user) return;

  if (user.role === "family") {
    routeTo("family");
    return;
  }

  if (user.role === "community" || user.role === "admin") {
    routeTo("community");
    return;
  }

  resetToDefaultPage();
}

function applyRegistrationLoginPrefill(payload: { username: string; password: string }) {
  loginUsername.value = payload.username;
  loginPassword.value = payload.password;
  authError.value = "";
}

function logout() {
  sessionUser.value = null;
  logoutSession();
  resetToDefaultPage();
}

watch(canAccessDebug, (allowed) => {
  if (!allowed && activePage.value === "debug") {
    const fallbackPage = allowedPages.value[0];
    if (fallbackPage && fallbackPage !== "none") {
      routeTo(fallbackPage);
      return;
    }
    resetToDefaultPage();
  }
});

onMounted(async () => {
  await restoreSession();
  initHashRouting();
});

onUnmounted(() => {
  disposeHashRouting();
});
</script>

<template>
  <LoginPage
    v-if="!isLoggedIn"
    :login-username="loginUsername"
    :login-password="loginPassword"
    :auth-loading="authLoading"
    :auth-error="authError"
    @update:login-username="loginUsername = $event"
    @update:login-password="loginPassword = $event"
    @submit-login="submitLogin"
    @prefill-login="applyRegistrationLoginPrefill"
  />

  <AppShell
    v-else-if="sessionUser"
    :session-user="sessionUser"
    :active-page="activePage"
    :allowed-pages="allowedPages"
    :can-access-debug="canAccessDebug"
    @logout="logout"
    @navigate="routeTo"
  >
    <DebugPage
      v-if="activePage === 'debug'"
      :can-go-community="allowedPages.includes('community')"
      @navigate="routeTo"
    />

    <CommunityPage
      v-else-if="activePage === 'community'"
      :session-user="sessionUser"
    />

    <FamilyPage
      v-else-if="activePage === 'family'"
      :session-user="sessionUser"
    />

    <MemberDevicePage
      v-else-if="activePage === 'relation'"
      :session-user="sessionUser"
    />

    <AccessDeniedPage v-else />
  </AppShell>
</template>
