<script setup lang="ts">
defineProps<{
  visible: boolean;
  title?: string;
  lead?: string;
  expectedSeconds?: number | null;
}>();
</script>

<template>
  <transition name="review-pending">
    <div v-if="visible" class="review-pending">
      <div class="review-pending__panel">
        <div class="review-pending__spinner" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <p class="review-pending__eyebrow">System Reviewing</p>
        <h3>{{ title || "系统正在复核现场，请稍等" }}</h3>
        <p>{{ lead || "已检测到异常姿态，系统正在结合快照进一步分析老人当前状态。" }}</p>
        <small v-if="expectedSeconds">通常需要 {{ expectedSeconds }} 秒左右。</small>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.review-pending {
  position: fixed;
  right: 26px;
  bottom: 26px;
  z-index: 1185;
  max-width: min(420px, calc(100vw - 32px));
}

.review-pending__panel {
  display: grid;
  gap: 10px;
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(9, 16, 34, 0.9);
  color: #f8fbff;
  box-shadow: 0 22px 60px rgba(9, 16, 34, 0.28);
  border: 1px solid rgba(122, 160, 255, 0.26);
}

.review-pending__eyebrow {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #93c5fd;
}

.review-pending__panel h3,
.review-pending__panel p,
.review-pending__panel small {
  margin: 0;
}

.review-pending__panel h3 {
  font-size: 1.12rem;
}

.review-pending__panel p {
  color: rgba(241, 245, 249, 0.88);
  line-height: 1.5;
}

.review-pending__panel small {
  color: rgba(191, 219, 254, 0.86);
}

.review-pending__spinner {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.review-pending__spinner span {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #60a5fa 0%, #34d399 100%);
  animation: review-pulse 1.2s ease-in-out infinite;
}

.review-pending__spinner span:nth-child(2) {
  animation-delay: 0.15s;
}

.review-pending__spinner span:nth-child(3) {
  animation-delay: 0.3s;
}

.review-pending-enter-active,
.review-pending-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.review-pending-enter-from,
.review-pending-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes review-pulse {
  0%, 80%, 100% {
    transform: scale(0.72);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
