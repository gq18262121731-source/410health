<script setup lang="ts">
defineProps<{
  variant?: "login" | "register" | "complete";
}>();
</script>

<template>
  <article class="panel login-panel login-panel--immersive auth-card" :class="`auth-card--${variant || 'login'}`">
    <slot />
  </article>
</template>
