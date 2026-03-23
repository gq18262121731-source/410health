<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { Bug, ChevronDown, Wrench } from "lucide-vue-next";
import type { PageKey } from "../../composables/useHashRouting";

const props = defineProps<{
  activePage: PageKey;
  canAccessDebug: boolean;
}>();

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

const isOpen = ref(false);
const menuRef = ref<HTMLElement | null>(null);

const debugActive = computed(() => props.activePage === "debug");

function closeMenu() {
  isOpen.value = false;
}

function toggleMenu() {
  isOpen.value = !isOpen.value;
}

function handleDocumentClick(event: MouseEvent) {
  if (!menuRef.value) return;
  if (event.target instanceof Node && !menuRef.value.contains(event.target)) {
    closeMenu();
  }
}

function goToDebug() {
  emit("navigate", "debug");
  closeMenu();
}

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
});

onUnmounted(() => {
  document.removeEventListener("click", handleDocumentClick);
});
</script>

<template>
  <div v-if="canAccessDebug" ref="menuRef" class="tool-entry">
    <button
      type="button"
      class="ghost-btn tool-entry__trigger"
      :class="{ active: isOpen || debugActive }"
      @click="toggleMenu"
    >
      <Wrench :size="15" />
      工具入口
      <ChevronDown :size="15" />
    </button>

    <div v-if="isOpen" class="tool-entry__panel">
      <button type="button" class="tool-entry__item" :class="{ active: debugActive }" @click="goToDebug">
        <span class="tool-entry__icon">
          <Bug :size="15" />
        </span>
        <span class="tool-entry__copy">
          <strong>调试看板</strong>
          <small>查看设备实时数据与趋势调试信息</small>
        </span>
      </button>
    </div>
  </div>
</template>
