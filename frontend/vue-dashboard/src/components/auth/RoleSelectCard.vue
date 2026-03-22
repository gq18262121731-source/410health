<script setup lang="ts">
defineProps<{
  badge: string;
  label: string;
  description: string;
  active?: boolean;
}>();

const emit = defineEmits<{
  select: [];
}>();
</script>

<template>
  <button type="button" class="register-role-card auth-role-select-card" :class="{ active }" @click="emit('select')">
    <span>{{ badge }}</span>
    <strong>{{ label }}</strong>
    <p>{{ description }}</p>
  </button>
</template>
