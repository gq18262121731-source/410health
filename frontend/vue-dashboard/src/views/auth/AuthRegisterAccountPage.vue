<script setup lang="ts">
import type { AuthFlowRole } from "../../composables/useAuthFlow";
import AuthFormField from "../../components/auth/AuthFormField.vue";
import AuthStepHeader from "../../components/auth/AuthStepHeader.vue";

defineProps<{
  role: AuthFlowRole;
  roleLabel: string;
  accountHint: string;
  draft: {
    name: string;
    phone: string;
    loginUsername: string;
    password: string;
    confirmPassword: string;
  };
  errorText: string;
}>();

const emit = defineEmits<{
  back: [];
  next: [];
  "update:name": [value: string];
  "update:phone": [value: string];
  "update:loginUsername": [value: string];
  "update:password": [value: string];
  "update:confirmPassword": [value: string];
}>();

function updateText(event: Event, field: "name" | "phone" | "loginUsername" | "password" | "confirmPassword") {
  const value = (event.target as HTMLInputElement).value;
  emit(`update:${field}` as never, value as never);
}
</script>

<template>
  <div class="auth-step-page">
    <AuthStepHeader
      eyebrow="第 2 步"
      title="注册账号"
      :subtitle="accountHint"
      :tag="roleLabel"
      back-label="返回身份选择"
      @back="emit('back')"
    />

    <div class="auth-form-grid auth-form-grid--two">
      <AuthFormField label="姓名">
        <input data-testid="auth-account-name" :value="draft.name" class="text-input" type="text" placeholder="请输入姓名" @input="updateText($event, 'name')" />
      </AuthFormField>

      <AuthFormField label="手机号">
        <input data-testid="auth-account-phone" :value="draft.phone" class="text-input" type="text" placeholder="请输入手机号" @input="updateText($event, 'phone')" />
      </AuthFormField>

      <AuthFormField v-if="role !== 'elder'" label="登录账号" note="可选，自定义登录账号。">
        <input data-testid="auth-account-login-username" :value="draft.loginUsername" class="text-input" type="text" placeholder="可选，自定义登录账号" @input="updateText($event, 'loginUsername')" />
      </AuthFormField>

      <AuthFormField label="设置密码">
        <input data-testid="auth-account-password" :value="draft.password" class="text-input" type="password" placeholder="请输入密码" @input="updateText($event, 'password')" />
      </AuthFormField>

      <AuthFormField class="auth-form-span-2" label="确认密码">
        <input data-testid="auth-account-confirm-password" :value="draft.confirmPassword" class="text-input" type="password" placeholder="请再次输入密码" @input="updateText($event, 'confirmPassword')" />
      </AuthFormField>
    </div>

    <p v-if="errorText" class="feedback-banner feedback-error">{{ errorText }}</p>

    <div class="auth-step-actions">
      <button type="button" class="ghost-btn" @click="emit('back')">返回身份选择</button>
      <button data-testid="auth-account-next" type="button" class="primary-btn" @click="emit('next')">进入资料完善</button>
    </div>
  </div>
</template>
