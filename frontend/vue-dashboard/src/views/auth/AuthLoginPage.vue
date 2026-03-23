<script setup lang="ts">
import heartImage from "../../assets/爱心.png";
import AuthFormField from "../../components/auth/AuthFormField.vue";

defineProps<{
  loginUsername: string;
  loginPassword: string;
  authLoading: boolean;
  authError: string;
}>();

const emit = defineEmits<{
  "update:loginUsername": [value: string];
  "update:loginPassword": [value: string];
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
    <div class="login-brand-inline" aria-label="系统品牌">
      <span class="login-brand-inline__icon">
        <img class="login-brand-inline__icon-image" :src="heartImage" alt="品牌图标" />
      </span>
      <span class="login-brand-inline__text">智慧养老健康监测平台</span>
    </div>

    <div class="login-card-header login-card-header--formal">
      <h2>账号登录</h2>
    </div>

    <form class="auth-step-body auth-form-stack auth-login-main" @submit.prevent="emit('submit')">
      <AuthFormField label="账号">
        <div class="login-field-control" :class="{ 'is-invalid': Boolean(authError) }">
          <span class="login-field-icon" aria-hidden="true">账</span>
          <input
            data-testid="login-username"
            :value="loginUsername"
            type="text"
            class="text-input login-input"
            placeholder="请输入账号"
            autocomplete="username"
            :disabled="authLoading"
            @input="updateText($event, 'username')"
          />
        </div>
      </AuthFormField>

      <AuthFormField label="密码">
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
          <span>{{ authLoading ? "登录中..." : "登录" }}</span>
        </button>
      </div>
    </form>

    <div class="login-compact-footer">
      <button type="button" class="text-link-btn text-link-btn--small" disabled>忘记密码</button>
      <button
        data-testid="open-registration"
        type="button"
        class="text-link-btn text-link-btn--small text-link-btn--strong"
        :disabled="authLoading"
        @click="emit('openRegister')"
      >
        注册账号
      </button>
    </div>
  </div>
</template>
