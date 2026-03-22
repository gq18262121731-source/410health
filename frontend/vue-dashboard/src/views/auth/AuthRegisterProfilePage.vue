<script setup lang="ts">
import type { AuthFlowRole } from "../../composables/useAuthFlow";
import AuthFormField from "../../components/auth/AuthFormField.vue";
import AuthStepHeader from "../../components/auth/AuthStepHeader.vue";

defineProps<{
  role: AuthFlowRole;
  profileTitle: string;
  profileDescription: string;
  bindPlanCopy: string;
  submitting: boolean;
  errorText: string;
  draft: {
    age: string;
    apartment: string;
    relationship: string;
    bindPlan: "now" | "later";
    landingChoice: "overview" | "report" | "alarm";
    shift: "day" | "night" | "flex";
    stationLabel: string;
  };
}>();

const emit = defineEmits<{
  back: [];
  submit: [];
  "update:age": [value: string];
  "update:apartment": [value: string];
  "update:relationship": [value: string];
  "update:bindPlan": [value: "now" | "later"];
  "update:landingChoice": [value: "overview" | "report" | "alarm"];
  "update:shift": [value: "day" | "night" | "flex"];
  "update:stationLabel": [value: string];
}>();

function updateInput(event: Event, field: "age" | "apartment" | "stationLabel") {
  const value = (event.target as HTMLInputElement).value;
  emit(`update:${field}` as never, value as never);
}

function updateSelect(event: Event, field: "relationship" | "landingChoice" | "shift") {
  const value = (event.target as HTMLSelectElement).value;
  emit(`update:${field}` as never, value as never);
}
</script>

<template>
  <div class="auth-step-page">
    <AuthStepHeader
      eyebrow="第 3 步"
      :title="profileTitle"
      :subtitle="profileDescription"
      back-label="返回账号注册"
      @back="emit('back')"
    />

    <div v-if="role === 'elder'" class="auth-form-grid auth-form-grid--two">
      <AuthFormField label="房间号">
        <input data-testid="auth-profile-apartment" :value="draft.apartment" class="text-input" type="text" placeholder="例如 A-302" @input="updateInput($event, 'apartment')" />
      </AuthFormField>
      <AuthFormField label="年龄">
        <input data-testid="auth-profile-age" :value="draft.age" class="text-input" type="number" min="1" placeholder="例如 78" @input="updateInput($event, 'age')" />
      </AuthFormField>
    </div>

    <div v-else-if="role === 'family'" class="auth-form-grid auth-form-grid--two">
      <AuthFormField label="关系类型">
        <select data-testid="auth-profile-relationship" class="inline-select relation-select" :value="draft.relationship" @change="updateSelect($event, 'relationship')">
          <option value="daughter">女儿</option>
          <option value="son">儿子</option>
          <option value="spouse">配偶</option>
          <option value="granddaughter">孙女</option>
          <option value="grandson">孙子</option>
          <option value="relative">其他亲属</option>
        </select>
      </AuthFormField>
      <AuthFormField label="进入系统后优先查看">
        <select data-testid="auth-profile-landing-choice" class="inline-select relation-select" :value="draft.landingChoice" @change="updateSelect($event, 'landingChoice')">
          <option value="report">健康报告</option>
          <option value="overview">当前状态概览</option>
          <option value="alarm">异常提醒</option>
        </select>
      </AuthFormField>
    </div>

    <div v-else class="auth-form-grid auth-form-grid--two">
      <AuthFormField label="值守班次">
        <select data-testid="auth-profile-shift" class="inline-select relation-select" :value="draft.shift" @change="updateSelect($event, 'shift')">
          <option value="day">日间值守</option>
          <option value="night">夜间值守</option>
          <option value="flex">灵活值守</option>
        </select>
      </AuthFormField>
      <AuthFormField label="值守站点">
        <input data-testid="auth-profile-station-label" :value="draft.stationLabel" class="text-input" type="text" placeholder="例如 海棠苑社区值守台" @input="updateInput($event, 'stationLabel')" />
      </AuthFormField>
      <AuthFormField class="auth-form-span-2" label="进入系统后优先查看">
        <select data-testid="auth-profile-community-landing-choice" class="inline-select relation-select" :value="draft.landingChoice" @change="updateSelect($event, 'landingChoice')">
          <option value="overview">社区总览</option>
          <option value="alarm">异常提醒</option>
          <option value="report">结构化报告</option>
        </select>
      </AuthFormField>
    </div>

    <div v-if="role !== 'community'" class="register-choice-panel auth-inline-panel">
      <div>
        <strong>设备绑定计划</strong>
        <p class="helper-copy">{{ bindPlanCopy }}</p>
      </div>
      <div class="mode-switch register-choice-switch">
        <button data-testid="auth-profile-bind-later" type="button" class="switch-btn mini-switch" :class="{ active: draft.bindPlan === 'later' }" @click="emit('update:bindPlan', 'later')">稍后绑定</button>
        <button data-testid="auth-profile-bind-now" type="button" class="switch-btn mini-switch" :class="{ active: draft.bindPlan === 'now' }" @click="emit('update:bindPlan', 'now')">尽快绑定</button>
      </div>
    </div>

    <p v-if="errorText" class="feedback-banner feedback-error">{{ errorText }}</p>

    <div class="auth-step-actions">
      <button type="button" class="ghost-btn" @click="emit('back')">返回账号注册</button>
      <button data-testid="auth-profile-submit" type="button" class="primary-btn" :disabled="submitting" @click="emit('submit')">
        {{ submitting ? "提交中..." : "完成资料并创建账号" }}
      </button>
    </div>
  </div>
</template>
