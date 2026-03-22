<script setup lang="ts">
import type { AuthFlowRole } from "../../composables/useAuthFlow";
import AuthStepHeader from "../../components/auth/AuthStepHeader.vue";

defineProps<{
  role: AuthFlowRole;
  successText: string;
  loginAccount: string;
  profileSummary: string[];
}>();

const emit = defineEmits<{
  back: [];
  prefill: [];
}>();
</script>

<template>
  <div class="auth-step-page">
    <AuthStepHeader
      eyebrow="第 4 步"
      title="注册完成，准备回到登录"
      subtitle="完成态负责承接“注册结束 → 回到登录 → 进入系统”这段体验，不让用户突然失去上下文。"
      back-label="返回资料完善"
      @back="emit('back')"
    />

    <div class="auth-complete-layout">
      <div class="register-result-mark">OK</div>
      <div class="auth-complete-copy">
        <p class="feedback-banner feedback-success">{{ successText }}</p>
        <div class="register-complete-grid auth-complete-grid">
          <article class="register-complete-card">
            <span>登录账号</span>
            <strong>{{ loginAccount }}</strong>
            <p>点击下方主按钮后，登录页会自动回填账号和密码，并给出清晰的回填提示。</p>
          </article>
          <article class="register-complete-card">
            <span>下一步</span>
            <strong>{{ role === "community" ? "进入社区总览" : role === "family" ? "进入家属端主链" : "先验证首登流程" }}</strong>
            <p>这一步只负责流程衔接，不伪造设备绑定、关系绑定或后端没有提供的后续能力。</p>
          </article>
        </div>

        <ul class="list-copy compact">
          <li v-for="item in profileSummary" :key="item">{{ item }}</li>
          <li>当前资料完善只展示真实接口已支持的结构化信息，不额外伪造业务结果。</li>
        </ul>
      </div>
    </div>

    <div class="auth-step-actions">
      <button type="button" class="ghost-btn" @click="emit('back')">返回资料完善</button>
      <button data-testid="auth-complete-prefill" type="button" class="primary-btn" @click="emit('prefill')">回到登录并自动回填</button>
    </div>
  </div>
</template>
