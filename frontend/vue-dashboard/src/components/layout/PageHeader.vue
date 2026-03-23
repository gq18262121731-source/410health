<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title: string;
  description?: string;
  meta?: string[];
}>();
</script>

<template>
  <header class="page-header panel">
    <div class="page-header__main">
      <p class="section-eyebrow">{{ eyebrow }}</p>
      <div class="page-header__top">
        <div class="page-header__copy">
          <h2>{{ title }}</h2>
          <p v-if="description" class="subtle-copy">{{ description }}</p>
        </div>
        <div v-if="$slots.actions" class="page-header__actions">
          <slot name="actions" />
        </div>
      </div>
      <div v-if="meta?.length" class="page-header__meta">
        <span v-for="item in meta" :key="item" class="meta-pill">{{ item }}</span>
      </div>
    </div>
    <div v-if="$slots.default" class="page-header__extra">
      <slot />
    </div>
  </header>
</template>
