<script setup lang="ts">
import type { AuthFlowRole } from "../../composables/useAuthFlow";
import AuthStepHeader from "../../components/auth/AuthStepHeader.vue";
import RoleSelectCard from "../../components/auth/RoleSelectCard.vue";

defineProps<{
  roles: ReadonlyArray<{
    key: AuthFlowRole;
    badge: string;
    label: string;
    description: string;
  }>;
  selectedRole: AuthFlowRole;
}>();

const emit = defineEmits<{
  back: [];
  selectRole: [role: AuthFlowRole];
  next: [];
}>();
</script>

<template>
  <div class="auth-step-page">
    <AuthStepHeader
      eyebrow="第 1 步"
      title="选择当前注册身份"
      subtitle="先确认注册对象，再进入账号创建和资料完善。整个流程用交互跳转推进，不再把所有内容堆成一页。"
      back-label="返回登录"
      @back="emit('back')"
    />

    <div class="auth-role-grid">
      <RoleSelectCard
        v-for="role in roles"
        :key="role.key"
        :badge="role.badge"
        :label="role.label"
        :description="role.description"
        :active="selectedRole === role.key"
        @select="emit('selectRole', role.key)"
      />
    </div>

    <div class="auth-step-actions">
      <span class="status-tag tone-info">当前身份：{{ roles.find((item) => item.key === selectedRole)?.label }}</span>
      <button data-testid="auth-role-next" type="button" class="primary-btn" @click="emit('next')">进入账号注册</button>
    </div>
  </div>
</template>
