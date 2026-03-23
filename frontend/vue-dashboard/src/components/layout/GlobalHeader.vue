<script setup lang="ts">
import { computed } from "vue";
import { Bell, LogOut, ShieldCheck } from "lucide-vue-next";
import type { SessionUser } from "../../api/client";

const props = defineProps<{
  sessionUser: SessionUser;
  activeAlarmCount: number;
}>();

const emit = defineEmits<{
  logout: [];
}>();

const roleLabel = computed(() => {
  switch (props.sessionUser.role) {
    case "community":
      return "社区角色";
    case "family":
      return "家属角色";
    case "admin":
      return "管理员";
    default:
      return "成员角色";
  }
});
</script>

<template>
  <header class="global-header panel">
    <div class="global-header__brand">
      <div class="brand-icon">护</div>
      <div class="global-header__brand-copy">
        <p class="section-eyebrow">AIoT Care Console</p>
        <h1>智慧养老健康监测平台</h1>
      </div>
    </div>

    <div class="global-header__meta">
      <span class="meta-pill meta-pill--icon">
        <Bell :size="14" />
        全局告警 {{ activeAlarmCount }}
      </span>
      <span class="meta-pill">{{ props.sessionUser.name }}</span>
      <span class="meta-pill meta-pill--icon">
        <ShieldCheck :size="14" />
        {{ roleLabel }}
      </span>
      <button type="button" class="ghost-btn global-header__logout" @click="emit('logout')">
        <LogOut :size="15" />
        退出
      </button>
    </div>
  </header>
</template>
