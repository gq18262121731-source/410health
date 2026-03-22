<script setup lang="ts">
import { computed } from "vue";
import type { AuthAccountPreview } from "../api/client";
import { useAuthFlow, type AuthFlowRole } from "../composables/useAuthFlow";
import AuthCard from "../components/auth/AuthCard.vue";
import QuickLoginPanel from "../components/auth/QuickLoginPanel.vue";
import AuthShell from "../components/auth/AuthShell.vue";
import AuthLoginPage from "./auth/AuthLoginPage.vue";
import AuthRegisterAccountPage from "./auth/AuthRegisterAccountPage.vue";
import AuthRegisterCompletePage from "./auth/AuthRegisterCompletePage.vue";
import AuthRegisterProfilePage from "./auth/AuthRegisterProfilePage.vue";
import AuthRoleSelectPage from "./auth/AuthRoleSelectPage.vue";

const props = defineProps<{
  loginUsername: string;
  loginPassword: string;
  authLoading: boolean;
  authError: string;
  authAccounts: AuthAccountPreview[];
  loginHelperAccount: string;
}>();

const emit = defineEmits<{
  "update:loginUsername": [value: string];
  "update:loginPassword": [value: string];
  "update:loginHelperAccount": [value: string];
  submitLogin: [];
  fillMockAccount: [];
  prefillLogin: [payload: { username: string; password: string; role: AuthFlowRole }];
}>();

const authFlow = useAuthFlow();

const loginHelperHint = computed(() =>
  props.authAccounts.length
    ? "已为当前演示准备正式账号，可直接填充进入不同角色页面。"
    : "当前没有预置演示账号，仍可手动输入真实账号。",
);

const loginDestinationLabel = computed(() => {
  if (authFlow.selectedRole.value === "community") return "社区总览";
  if (authFlow.selectedRole.value === "elder") return "首登体验";
  return "家属端健康总览";
});

const loginSupportTips = computed(() =>
  authFlow.selectedRole.value === "community"
    ? [
        "社区账号登录后优先进入社区总览，可继续处理成员与设备页和重点对象。",
        "如果刚完成注册，返回登录后会直接使用系统已回填的账号。",
        "如账号不可用，请先确认公共注册接口和正式登录接口处于在线状态。",
      ]
    : authFlow.selectedRole.value === "elder"
      ? [
          "老人账号主要用于演示登录和首登链路，业务页权限仍以后端角色控制为准。",
          "完成注册后可先回到登录页，确认账号回填和完成态衔接是否自然。",
          "如果需要完整业务链路演示，建议继续使用家属或社区账号。",
        ]
      : [
          "家属账号登录后优先看到当前状态、评估报告和异常升级链路。",
          "如果刚完成注册，返回登录后系统会自动回填可用账号。",
          "如果老人尚未绑定设备，登录后会先显示基础建议和绑定提示。",
        ],
);

function handlePrefill() {
  const payload = authFlow.consumePrefillPayload();
  if (!payload) return;
  emit("prefillLogin", payload);
}
</script>

<template>
  <AuthShell :compact-hero="authFlow.currentStep.value !== 'login'">
    <template #hero>
      <p class="section-eyebrow">健康监测演示入口</p>
      <h1>智慧养老系统登录与注册</h1>
      <p class="lead">
        登录链路已经拆成更清晰的五步：登录、身份选择、账号注册、资料完善、完成回填。
        页面只负责展示和交互，真实登录与会话仍只保留在 `useSessionAuth` 一份状态里。
      </p>
      <div class="login-hero-badges">
        <span class="status-tag tone-stable">绿色基调</span>
        <span class="status-tag tone-info">ECG 动态背景</span>
        <span class="status-tag tone-neutral">移动端轻量降级</span>
      </div>
      <ul class="login-hero-points">
        <li>正式登录与公共注册都保持真实接口接法。</li>
        <li>注册完成后自动回填账号与密码，直接衔接回登录步骤。</li>
      </ul>
    </template>

    <AuthCard>
      <AuthLoginPage
        v-if="authFlow.currentStep.value === 'login'"
        :login-username="loginUsername"
        :login-password="loginPassword"
        :auth-loading="authLoading"
        :auth-error="authError"
        :destination-label="loginDestinationLabel"
        :support-tips="loginSupportTips"
        :prefill-notice="authFlow.prefillNotice.value"
        :show-help="authFlow.showHelp.value"
        @update:login-username="emit('update:loginUsername', $event)"
        @update:login-password="emit('update:loginPassword', $event)"
        @update:show-help="authFlow.showHelp.value = $event"
        @submit="emit('submitLogin')"
        @open-register="authFlow.openRoleSelect()"
      />

      <AuthRoleSelectPage
        v-else-if="authFlow.currentStep.value === 'role-select'"
        :roles="authFlow.authRoleOptions"
        :selected-role="authFlow.selectedRole.value"
        @back="authFlow.goToLogin()"
        @select-role="authFlow.selectRole($event)"
        @next="authFlow.goToRegisterAccount()"
      />

      <AuthRegisterAccountPage
        v-else-if="authFlow.currentStep.value === 'register-account'"
        :role="authFlow.selectedRole.value"
        :role-label="authFlow.activeRole.value.label"
        :account-hint="authFlow.activeRole.value.accountHint"
        :draft="authFlow.accountDraft.value"
        :error-text="authFlow.registrationError.value"
        @back="authFlow.goBack('role-select')"
        @next="authFlow.goToRegisterProfile()"
        @update:name="authFlow.accountDraft.value.name = $event"
        @update:phone="authFlow.accountDraft.value.phone = $event"
        @update:login-username="authFlow.accountDraft.value.loginUsername = $event"
        @update:password="authFlow.accountDraft.value.password = $event"
        @update:confirm-password="authFlow.accountDraft.value.confirmPassword = $event"
      />

      <AuthRegisterProfilePage
        v-else-if="authFlow.currentStep.value === 'register-profile'"
        :role="authFlow.selectedRole.value"
        :profile-title="authFlow.activeRole.value.profileTitle"
        :profile-description="authFlow.activeRole.value.profileDescription"
        :bind-plan-copy="authFlow.bindPlanCopy.value"
        :submitting="authFlow.registrationSubmitting.value"
        :error-text="authFlow.registrationError.value"
        :draft="authFlow.profileDraft.value"
        @back="authFlow.goBack('register-account')"
        @submit="void authFlow.submitRegistration()"
        @update:age="authFlow.profileDraft.value.age = $event"
        @update:apartment="authFlow.profileDraft.value.apartment = $event"
        @update:relationship="authFlow.profileDraft.value.relationship = $event"
        @update:bind-plan="authFlow.profileDraft.value.bindPlan = $event"
        @update:landing-choice="authFlow.profileDraft.value.landingChoice = $event"
        @update:shift="authFlow.profileDraft.value.shift = $event"
        @update:station-label="authFlow.profileDraft.value.stationLabel = $event"
      />

      <AuthRegisterCompletePage
        v-else
        :role="authFlow.selectedRole.value"
        :success-text="authFlow.registrationSuccess.value"
        :login-account="authFlow.completedCredentials.value?.username || authFlow.currentLoginAccount.value"
        :profile-summary="authFlow.profileSummary.value"
        @back="authFlow.goBack('register-profile')"
        @prefill="handlePrefill"
      />
    </AuthCard>

    <QuickLoginPanel
      v-if="authFlow.currentStep.value === 'login'"
      :accounts="authAccounts"
      :helper-text="loginHelperHint"
      :selected-account="loginHelperAccount"
      :disabled="authLoading"
      @update:selected-account="emit('update:loginHelperAccount', $event)"
      @fill="emit('fillMockAccount')"
    />
  </AuthShell>
</template>
