<script setup lang="ts">
import AuthFormField from "../../components/auth/AuthFormField.vue";
import AuthStepHeader from "../../components/auth/AuthStepHeader.vue";

defineProps<{
  loginUsername: string;
  loginPassword: string;
  authLoading: boolean;
  authError: string;
  destinationLabel: string;
  supportTips: string[];
  prefillNotice: string;
  showHelp: boolean;
}>();

const emit = defineEmits<{
  "update:loginUsername": [value: string];
  "update:loginPassword": [value: string];
  "update:showHelp": [value: boolean];
  submit: [];
  openRegister: [];
}>();

function updateText(event: Event, field: "username" | "password") {
  const value = (event.target as HTMLInputElement).value;
  if (field === "username") {
    emit("update:loginUsername", value);
    return;
  }
  emit("update:loginPassword", value);
}
</script>

<template>
  <div class="auth-step-page auth-step-page--login">
    <AuthStepHeader
      eyebrow="登录入口"
      title="登录账户"
      subtitle="登录状态只保留一份，会话与真实登录仍由 useSessionAuth 统一管理。"
      tag="轻玻璃拟态"
    />

    <form class="auth-step-body auth-form-stack auth-login-main" @submit.prevent="emit('submit')">
      <p v-if="prefillNotice" data-testid="login-prefill-banner" class="feedback-banner feedback-success login-prefill-banner">{{ prefillNotice }}</p>

      <AuthFormField label="账号" note="支持账号名、登录名或手机号。">
        <div class="login-field-control" :class="{ 'is-invalid': Boolean(authError) }">
          <span class="login-field-icon" aria-hidden="true">账</span>
          <input
            data-testid="login-username"
            :value="loginUsername"
            type="text"
            class="text-input login-input"
            placeholder="请输入账号或手机号"
            autocomplete="username"
            :disabled="authLoading"
            @input="updateText($event, 'username')"
          />
        </div>
      </AuthFormField>

      <AuthFormField label="密码" :note="`登录后将优先进入${destinationLabel}。`">
        <div class="login-field-control" :class="{ 'is-invalid': Boolean(authError) }">
          <span class="login-field-icon" aria-hidden="true">密</span>
          <input
            data-testid="login-password"
            :value="loginPassword"
            type="password"
            class="text-input login-input"
            placeholder="请输入密码"
            autocomplete="current-password"
            :disabled="authLoading"
            @input="updateText($event, 'password')"
          />
        </div>
      </AuthFormField>

      <p v-if="authError" data-testid="login-error-banner" class="feedback-banner feedback-error">{{ authError }}</p>

      <div class="auth-step-actions auth-step-actions--full">
        <button
          data-testid="login-submit"
          type="submit"
          class="primary-btn login-submit login-submit--primary"
          :disabled="authLoading || !loginUsername.trim() || !loginPassword.trim()"
        >
          <span v-if="authLoading" class="login-btn-spinner" aria-hidden="true"></span>
          <span>{{ authLoading ? "正在验证身份..." : `登录并进入${destinationLabel}` }}</span>
        </button>
      </div>
    </form>

    <section class="auth-login-meta">
      <div class="auth-login-links">
        <button type="button" class="text-link-btn text-link-btn--small" @click="emit('update:showHelp', true)">忘记密码？</button>
        <button type="button" class="text-link-btn text-link-btn--small" @click="emit('update:showHelp', !showHelp)">
          {{ showHelp ? "收起说明" : "登录说明" }}
        </button>
      </div>
      <div v-if="showHelp" class="login-help-panel auth-login-help-panel">
        <strong>登录说明</strong>
        <ul class="list-copy compact">
          <li v-for="item in supportTips" :key="item">{{ item }}</li>
        </ul>
      </div>
      <p class="auth-register-copy">
        还没有账号？
        <button data-testid="open-registration" type="button" class="text-link-btn text-link-btn--small text-link-btn--strong" :disabled="authLoading" @click="emit('openRegister')">
          立即注册
        </button>
      </p>
    </section>
  </div>
</template>
