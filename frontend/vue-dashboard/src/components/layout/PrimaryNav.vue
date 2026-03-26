<script setup lang="ts">
import { computed } from "vue";
import {
  Activity,
  Cpu,
  Network,
  SquareTerminal,
  type LucideIcon,
  UsersRound,
} from "lucide-vue-next";
import type { PageKey } from "../../composables/useHashRouting";

const props = defineProps<{
  activePage: PageKey;
  allowedPages: PageKey[];
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

type NavItem = {
  page: PageKey;
  label: string;
  description: string;
  icon: LucideIcon;
};

const navItems = computed<NavItem[]>(() =>
  ([
    {
      page: "overview" as PageKey,
      label: "总览监护",
      description: "实时曲线与告警",
      icon: Activity,
    },
    {
      page: "topology" as PageKey,
      label: "设备拓扑",
      description: "老人、家属与设备关系",
      icon: Network,
    },
    {
      page: "members" as PageKey,
      label: "成员设备",
      description: "注册、绑定与台账",
      icon: UsersRound,
    },
    {
      page: "agent" as PageKey,
      label: "智能体工作台",
      description: "问答、分析与工具",
      icon: SquareTerminal,
    },
    {
      page: "family" as PageKey,
      label: "家属视图",
      description: "家庭成员查看页面",
      icon: Cpu,
    },
  ] satisfies NavItem[]).filter((item) => props.allowedPages.includes(item.page)),
);
</script>

<template>
  <nav v-if="navItems.length" class="primary-nav" aria-label="主导航">
    <button
      v-for="item in navItems"
      :key="item.page"
      type="button"
      class="primary-nav__item"
      :class="{ active: activePage === item.page }"
      @click="emit('navigate', item.page)"
    >
      <component :is="item.icon" :size="18" />
      <span class="primary-nav__copy">
        <strong>{{ item.label }}</strong>
        <small>{{ item.description }}</small>
      </span>
    </button>
  </nav>
</template>
