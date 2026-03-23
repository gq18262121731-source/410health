<script setup lang="ts">
import { computed } from "vue";
import AuthCard from "../components/auth/AuthCard.vue";
import AuthShell from "../components/auth/AuthShell.vue";
import { useAuthFlow, type AuthCompletedCredentials, type AuthFlowRole } from "../composables/useAuthFlow";
import AuthLoginPage from "./auth/AuthLoginPage.vue";
import RegisterFlow from "./auth/RegisterFlow.vue";

defineProps<{
  loginUsername: string;
  loginPassword: string;
  authLoading: boolean;
  authError: string;
}>();

const emit = defineEmits<{
  "update:loginUsername": [value: string];
  "update:loginPassword": [value: string];
  submitLogin: [];
  prefillLogin: [payload: { username: string; password: string; role: AuthFlowRole }];
}>();

const authFlow = useAuthFlow();

const authCardVariant = computed(() => {
  return authFlow.currentStep.value === "register" ? "register" : "login";
});

function handleRegistrationComplete(payload: AuthCompletedCredentials) {
  authFlow.goToLogin();
  emit("prefillLogin", payload);
}
</script>

<template>
  <AuthShell>
    <AuthCard :variant="authCardVariant">
      <AuthLoginPage
        v-if="authFlow.currentStep.value === 'login'"
        :login-username="loginUsername"
        :login-password="loginPassword"
        :auth-loading="authLoading"
        :auth-error="authError"
        @update:login-username="emit('update:loginUsername', $event)"
        @update:login-password="emit('update:loginPassword', $event)"
        @submit="emit('submitLogin')"
        @open-register="authFlow.openRegister()"
      />

      <RegisterFlow
        v-else-if="authFlow.currentStep.value === 'register'"
        @cancel="authFlow.goToLogin()"
        @complete="handleRegistrationComplete"
      />
    </AuthCard>
  </AuthShell>
</template>
