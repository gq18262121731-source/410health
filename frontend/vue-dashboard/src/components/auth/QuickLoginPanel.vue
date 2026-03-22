<script setup lang="ts">
import type { AuthAccountPreview } from "../../api/client";

defineProps<{
  accounts: AuthAccountPreview[];
  helperText: string;
  selectedAccount: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:selectedAccount": [value: string];
  fill: [];
}>();

function updateSelect(event: Event) {
  emit("update:selectedAccount", (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <article class="demo-account-panel demo-account-panel--floating auth-quick-login">
    <div class="demo-account-head">
      <div>
        <h3>演示账号快捷进入</h3>
        <p class="panel-subtitle">{{ helperText }}</p>
      </div>
      <button type="button" class="ghost-btn login-quickfill-btn" :disabled="disabled || !accounts.length" @click="emit('fill')">一键填充</button>
    </div>
    <div class="login-quickfill-row">
      <select class="inline-select" :value="selectedAccount" :disabled="disabled || !accounts.length" @change="updateSelect">
        <option v-for="account in accounts" :key="account.username" :value="account.username">
          {{ account.display_name }} / {{ account.role }} / {{ account.username }}
        </option>
      </select>
      <span class="helper-copy">选中演示账号后可直接回填到登录表单，正式注册成功后也会回到同样的回填体验。</span>
    </div>
  </article>
</template>
