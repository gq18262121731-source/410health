<script setup lang="ts">
import { computed } from "vue";
import { api, type AlarmRecord } from "../../api/client";

const props = defineProps<{
  alarm: AlarmRecord | null;
  additionalCount: number;
  acknowledging?: boolean;
}>();

const emit = defineEmits<{
  acknowledge: [];
}>();

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

const eventPayload = computed(() => asRecord(props.alarm?.metadata?.event));
const injuryPayload = computed(() => asRecord(eventPayload.value?.injury));

const triggeredAt = computed(() => {
  if (!props.alarm?.created_at) return "--";
  return new Date(props.alarm.created_at).toLocaleString("zh-CN", { hour12: false });
});

const fallScore = computed(() => {
  const score = eventPayload.value?.fall_score;
  return typeof score === "number" ? `${Math.round(score * 100)}%` : "--";
});

const injuryLevel = computed(() => {
  const level = injuryPayload.value?.level;
  return typeof level === "string" && level.trim() ? level : "待评估";
});

const severity = computed(() => {
  const value = eventPayload.value?.severity;
  return typeof value === "string" && value.trim() ? value : "L?";
});

const advice = computed(() => {
  const value = injuryPayload.value?.advice;
  return typeof value === "string" && value.trim() ? value : "请值守人员立即查看实时画面，并联系现场照护人员确认老人状态。";
});

const snapshotUrl = computed(() => {
  const path = eventPayload.value?.snapshot_path;
  return typeof path === "string" && path.trim() ? api.getCameraFallSnapshotUrl(path) : "";
});
</script>

<template>
  <transition name="fall-overlay">
    <div v-if="alarm" class="fall-overlay">
      <div class="fall-overlay__panel">
        <div class="fall-overlay__content">
          <p class="fall-overlay__eyebrow">Fall Detection Alert</p>
          <h2>检测到疑似跌倒</h2>
          <p class="fall-overlay__lead">
            系统已从监控视频识别到高风险跌倒事件，请立即核对画面、联系照护人员，并记录处理结果。
          </p>

          <div class="fall-overlay__grid">
            <article>
              <span>摄像头/设备</span>
              <strong>{{ alarm.device_mac }}</strong>
            </article>
            <article>
              <span>触发时间</span>
              <strong>{{ triggeredAt }}</strong>
            </article>
            <article>
              <span>跌倒置信度</span>
              <strong>{{ fallScore }}</strong>
            </article>
            <article>
              <span>风险等级</span>
              <strong>{{ severity }} / {{ injuryLevel }}</strong>
            </article>
          </div>

          <p class="fall-overlay__advice">{{ advice }}</p>

          <div class="fall-overlay__actions">
            <p v-if="additionalCount > 0">还有 {{ additionalCount }} 条跌倒告警等待处理。</p>
            <p v-else></p>
            <button type="button" :disabled="acknowledging" @click="emit('acknowledge')">
              {{ acknowledging ? "处理中..." : "确认处理并解除警报" }}
            </button>
          </div>
        </div>

        <div class="fall-overlay__snapshot">
          <img v-if="snapshotUrl" :src="snapshotUrl" alt="跌倒告警截图" />
          <div v-else class="fall-overlay__snapshot-empty">等待模型截图</div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.fall-overlay {
  position: fixed;
  inset: 0;
  z-index: 1190;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(24, 37, 64, 0.74);
  backdrop-filter: blur(10px);
}

.fall-overlay__panel {
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 20px;
  padding: 24px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(239, 246, 255, 0.94));
  box-shadow: 0 28px 90px rgba(15, 23, 42, 0.34);
}

.fall-overlay__content {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.fall-overlay__eyebrow {
  margin: 0;
  color: #b42318;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.fall-overlay h2 {
  margin: 0;
  color: #111827;
  font-size: clamp(2rem, 4vw, 3.1rem);
  line-height: 1.05;
}

.fall-overlay__lead,
.fall-overlay__advice,
.fall-overlay__actions p {
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

.fall-overlay__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.fall-overlay__grid article {
  display: grid;
  gap: 7px;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid #dbe4f0;
  background: #ffffff;
}

.fall-overlay__grid span {
  color: #64748b;
  font-size: 0.82rem;
  font-weight: 700;
}

.fall-overlay__grid strong {
  color: #0f172a;
  line-height: 1.45;
  word-break: break-word;
}

.fall-overlay__advice {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(239, 68, 68, 0.22);
  background: rgba(254, 242, 242, 0.82);
  color: #7f1d1d;
}

.fall-overlay__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.fall-overlay__actions button {
  flex-shrink: 0;
  border: none;
  border-radius: 999px;
  padding: 13px 20px;
  background: #b42318;
  color: #fff;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(180, 35, 24, 0.22);
}

.fall-overlay__actions button:disabled {
  cursor: wait;
  opacity: 0.68;
}

.fall-overlay__snapshot {
  min-height: 360px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  background: #0f172a;
}

.fall-overlay__snapshot img {
  width: 100%;
  height: 100%;
  min-height: 360px;
  object-fit: cover;
  display: block;
}

.fall-overlay__snapshot-empty {
  height: 100%;
  min-height: 360px;
  display: grid;
  place-items: center;
  color: #cbd5e1;
  font-weight: 700;
}

.fall-overlay-enter-active,
.fall-overlay-leave-active {
  transition: opacity 180ms ease;
}

.fall-overlay-enter-from,
.fall-overlay-leave-to {
  opacity: 0;
}

@media (max-width: 840px) {
  .fall-overlay {
    padding: 16px;
    align-items: start;
    overflow-y: auto;
  }

  .fall-overlay__panel {
    grid-template-columns: 1fr;
    padding: 18px;
  }

  .fall-overlay__grid {
    grid-template-columns: 1fr;
  }

  .fall-overlay__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .fall-overlay__snapshot,
  .fall-overlay__snapshot img,
  .fall-overlay__snapshot-empty {
    min-height: 240px;
  }
}
</style>
