<script setup lang="ts">
import { computed } from "vue";
import type { PageKey } from "../../composables/useHashRouting";

const props = defineProps<{
  activePage: PageKey;
  allowedPages: PageKey[];
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const navItems = computed(() =>
  [
    { page: "community" as const, label: "社区总览" },
    { page: "family" as const, label: "家属视图" },
    { page: "relation" as const, label: "成员与设备" },
  ].filter((item) => props.allowedPages.includes(item.page)),
);
</script>

<template>
  <nav v-if="navItems.length" class="primary-nav panel" aria-label="主导航">
    <button
      v-for="item in navItems"
      :key="item.page"
      type="button"
      class="primary-nav__item"
      :class="{ active: activePage === item.page }"
      @click="emit('navigate', item.page)"
    >
      {{ item.label }}
    </button>
  </nav>
</template>
