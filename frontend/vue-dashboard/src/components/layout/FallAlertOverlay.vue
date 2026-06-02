<script setup lang="ts">
import { computed, ref, watch } from "vue";
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
const multimodalReview = computed(() => asRecord(eventPayload.value?.multimodal_review));
const presentation = computed(() => asRecord(props.alarm?.metadata?.presentation) ?? asRecord(eventPayload.value?.presentation));
const familyGuidance = computed(() => asRecord(props.alarm?.metadata?.family_guidance));
const snapshotFailed = ref(false);

watch(
  () => props.alarm?.id,
  () => {
    snapshotFailed.value = false;
  },
);

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
  return typeof level === "string" && level.trim() ? level : "Pending";
});

const severity = computed(() => {
  const value = eventPayload.value?.severity;
  return typeof value === "string" && value.trim() ? value : "L?";
});

const advice = computed(() => {
  const guidanceActions = familyGuidance.value?.immediate_actions;
  if (Array.isArray(guidanceActions) && guidanceActions.length > 0) {
    return guidanceActions.filter((item) => typeof item === "string" && item.trim()).slice(0, 3).join("；");
  }
  const actions = presentation.value?.recommended_actions;
  if (Array.isArray(actions) && actions.length > 0) {
    return actions.filter((item) => typeof item === "string" && item.trim()).slice(0, 2).join("；");
  }
  const value = injuryPayload.value?.advice;
  return typeof value === "string" && value.trim()
    ? value
    : "请立即查看现场视频，并尽快确认老人状态。";
});

const guidanceActions = computed(() => {
  const actions = familyGuidance.value?.immediate_actions;
  return Array.isArray(actions) ? actions.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
});

const contraindications = computed(() => {
  const items = familyGuidance.value?.contraindications;
  return Array.isArray(items) ? items.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
});

const severityLabel = computed(() => {
  const label = familyGuidance.value?.severity_label;
  return typeof label === "string" && label.trim() ? label : "";
});

const familyMessage = computed(() => {
  const value = familyGuidance.value?.family_message;
  return typeof value === "string" && value.trim() ? value : "";
});

const shouldCallEmergency = computed(() => familyGuidance.value?.call_emergency === true);

const snapshotUrl = computed(() => {
  if (snapshotFailed.value) return "";
  const directUrl = eventPayload.value?.snapshot_url;
  const path = eventPayload.value?.snapshot_path;
  const value = typeof directUrl === "string" && directUrl.trim() ? directUrl : path;
  return typeof value === "string" && value.trim() ? api.getCameraFallSnapshotUrl(value) : "";
});

const reviewJudgement = computed(() => {
  const value = multimodalReview.value?.judgement;
  if (typeof value !== "string" || !value.trim()) return "not_available";
  return value;
});

const reviewConfidence = computed(() => {
  const value = multimodalReview.value?.confidence;
  return typeof value === "string" && value.trim() ? value : "--";
});

const reviewReason = computed(() => {
  const value = multimodalReview.value?.reason;
  return typeof value === "string" && value.trim() ? value : "";
});

const reviewAction = computed(() => {
  const value = multimodalReview.value?.recommended_action;
  return typeof value === "string" && value.trim() ? value : "";
});

const reviewSuppressesStrongAlert = computed(
  () =>
    reviewJudgement.value === "no_fall" &&
    (["medium", "high"].includes(reviewConfidence.value) || reviewAction.value === "downgrade"),
);

const reviewLabel = computed(() => {
  switch (reviewJudgement.value) {
    case "fall":
      return "Second review keeps the fall alarm";
    case "possible_fall":
      return "Second review suggests human verification";
    case "no_fall":
      return reviewSuppressesStrongAlert.value
        ? "Second review leans to false alarm"
        : "Second review leans to false alarm, but confidence is still low";
    case "uncertain":
      return "Second review is inconclusive";
    default:
      return "Second review unavailable";
  }
});

const reviewTone = computed(() => {
  switch (reviewJudgement.value) {
    case "fall":
      return "keep";
    case "possible_fall":
      return "review";
    case "no_fall":
      return reviewSuppressesStrongAlert.value ? "downgrade" : "neutral";
    case "uncertain":
      return "neutral";
    default:
      return "neutral";
  }
});

const reviewMeta = computed(() => {
  const parts: string[] = [];
  if (reviewConfidence.value !== "--") {
    parts.push(`Confidence ${reviewConfidence.value}`);
  }
  if (reviewAction.value) {
    parts.push(`Action ${reviewAction.value}`);
  }
  return parts.join(" · ");
});

const alertEyebrow = computed(() => {
  switch (reviewJudgement.value) {
    case "fall":
      return "复核确认跌倒";
    case "possible_fall":
      return "跌倒告警待人工复核";
    case "no_fall":
      return reviewSuppressesStrongAlert.value ? "复核后已降级" : "复核后仍建议关注";
    case "uncertain":
      return "系统仍在谨慎判断";
    default:
      return "跌倒检测告警";
  }
});

const alertTitle = computed(() => {
  const title = presentation.value?.title;
  if (typeof title === "string" && title.trim()) return title;
  switch (reviewJudgement.value) {
    case "fall":
      return "高风险跌倒已确认";
    case "possible_fall":
      return "疑似跌倒，请人工复核";
    case "no_fall":
      return reviewSuppressesStrongAlert.value
        ? "系统复核后倾向于误报"
        : "疑似跌倒仍需继续确认";
    case "uncertain":
      return "当前异常仍需进一步观察";
    default:
      return "检测到疑似跌倒";
  }
});

const alertLead = computed(() => {
  const lead = presentation.value?.lead;
  if (typeof lead === "string" && lead.trim()) return lead;
  switch (reviewJudgement.value) {
    case "fall":
      return "第一轮检测和第二轮复核都支持保留这条跌倒告警。";
    case "possible_fall":
      return "系统已发现高风险异常姿态，建议立即查看现场并人工确认。";
    case "no_fall":
      return reviewSuppressesStrongAlert.value
        ? "第二轮复核更倾向于误报，但仍建议短时人工确认后再关闭提醒。"
        : "第二轮复核暂时倾向于误报，但信心还不够高，请继续查看现场。";
    case "uncertain":
      return "系统已检测到异常，但仅凭当前快照还不能得出完全明确的结论。";
    default:
      return "系统已检测到跌倒相关异常，请立即查看现场并确认是否需要协助。";
  }
});

const acknowledgeLabel = computed(() => {
  if (props.acknowledging) return "Processing...";
  switch (reviewJudgement.value) {
    case "fall":
      return "Acknowledge and keep follow-up";
    case "possible_fall":
      return "Acknowledge after manual review";
    case "no_fall":
      return reviewSuppressesStrongAlert.value ? "Acknowledge downgraded alert" : "Acknowledge after manual review";
    case "uncertain":
      return "Acknowledge after manual review";
    default:
      return "Acknowledge and dismiss";
  }
});
</script>

<template>
  <transition name="fall-overlay">
    <div v-if="alarm" class="fall-overlay">
      <div class="fall-overlay__panel">
        <div class="fall-overlay__content">
          <p class="fall-overlay__eyebrow">{{ alertEyebrow }}</p>
          <h2>{{ alertTitle }}</h2>
          <p class="fall-overlay__lead">{{ alertLead }}</p>

          <div class="fall-overlay__grid">
            <article>
              <span>Camera device</span>
              <strong>{{ alarm.device_mac }}</strong>
            </article>
            <article>
              <span>Triggered at</span>
              <strong>{{ triggeredAt }}</strong>
            </article>
            <article>
              <span>Fall score</span>
              <strong>{{ fallScore }}</strong>
            </article>
            <article>
              <span>Severity</span>
              <strong>{{ severityLabel || `${severity} / ${injuryLevel}` }}</strong>
            </article>
          </div>

          <p class="fall-overlay__advice">{{ advice }}</p>
          <div v-if="guidanceActions.length" class="fall-overlay__guidance">
            <strong>家属应对措施</strong>
            <ul>
              <li v-for="item in guidanceActions" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div v-if="contraindications.length" class="fall-overlay__guidance fall-overlay__guidance--warn">
            <strong>注意事项</strong>
            <ul>
              <li v-for="item in contraindications" :key="item">{{ item }}</li>
            </ul>
          </div>
          <p v-if="familyMessage" class="fall-overlay__family-message">{{ familyMessage }}</p>
          <p v-if="shouldCallEmergency" class="fall-overlay__emergency">建议立即准备急救或医疗支援。</p>

          <div class="fall-overlay__review" :class="`fall-overlay__review--${reviewTone}`">
            <div class="fall-overlay__review-head">
              <span class="fall-overlay__review-eyebrow">Multimodal second review</span>
              <strong>{{ reviewLabel }}</strong>
            </div>
            <p v-if="reviewMeta" class="fall-overlay__review-meta">{{ reviewMeta }}</p>
            <p v-if="reviewReason" class="fall-overlay__review-reason">{{ reviewReason }}</p>
          </div>

          <div class="fall-overlay__actions">
            <p v-if="additionalCount > 0">{{ additionalCount }} more fall alarms waiting.</p>
            <p v-else></p>
            <button type="button" :disabled="acknowledging" @click="emit('acknowledge')">
              {{ acknowledgeLabel }}
            </button>
          </div>
        </div>

        <div class="fall-overlay__snapshot">
          <img v-if="snapshotUrl" :src="snapshotUrl" alt="fall snapshot" @error="snapshotFailed = true" />
          <div v-else class="fall-overlay__snapshot-empty">截图暂不可用，请查看实时视频画面</div>
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
  padding: 16px;
  background: rgba(24, 37, 64, 0.74);
  backdrop-filter: blur(10px);
}

.fall-overlay__panel {
  width: min(1080px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.85fr);
  gap: 14px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(239, 246, 255, 0.94));
  box-shadow: 0 28px 90px rgba(15, 23, 42, 0.34);
  overflow: hidden;
}

.fall-overlay__content {
  display: grid;
  gap: 10px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
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
  font-size: clamp(1.6rem, 3vw, 2.35rem);
  line-height: 1.05;
}

.fall-overlay__lead,
.fall-overlay__advice,
.fall-overlay__actions p {
  margin: 0;
  color: #475569;
  line-height: 1.5;
}

.fall-overlay__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.fall-overlay__grid article {
  display: grid;
  gap: 5px;
  padding: 10px 12px;
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
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(239, 68, 68, 0.22);
  background: rgba(254, 242, 242, 0.82);
  color: #7f1d1d;
}

.fall-overlay__guidance {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 10px;
  background: rgba(254, 242, 242, 0.82);
  color: #7f1d1d;
}

.fall-overlay__guidance--warn {
  background: rgba(255, 251, 235, 0.9);
  border-color: rgba(251, 191, 36, 0.34);
}

.fall-overlay__guidance strong {
  display: block;
  margin-bottom: 6px;
}

.fall-overlay__guidance ul {
  margin: 0;
  padding-left: 20px;
}

.fall-overlay__guidance li {
  margin: 3px 0;
  line-height: 1.35;
}

.fall-overlay__family-message,
.fall-overlay__emergency {
  margin: 12px 0 0;
  color: #7f1d1d;
  font-weight: 700;
  line-height: 1.35;
}

.fall-overlay__emergency {
  color: #b42318;
}

.fall-overlay__review {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #dbe4f0;
  background: #ffffff;
}

.fall-overlay__review--keep {
  border-color: rgba(180, 35, 24, 0.28);
  background: rgba(254, 242, 242, 0.66);
}

.fall-overlay__review--review {
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(255, 251, 235, 0.9);
}

.fall-overlay__review--downgrade {
  border-color: rgba(8, 145, 178, 0.24);
  background: rgba(240, 249, 255, 0.92);
}

.fall-overlay__review--neutral {
  border-color: #dbe4f0;
  background: #ffffff;
}

.fall-overlay__review-head {
  display: grid;
  gap: 4px;
}

.fall-overlay__review-eyebrow {
  color: #64748b;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.fall-overlay__review-head strong,
.fall-overlay__review-meta,
.fall-overlay__review-reason {
  margin: 0;
  color: #334155;
  line-height: 1.6;
}

.fall-overlay__review-reason {
  color: #475569;
}

.fall-overlay__actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  position: sticky;
  bottom: 0;
  z-index: 1;
  padding-top: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(248, 250, 252, 0.96) 35%);
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
  min-height: 0;
  min-width: 0;
  height: 100%;
  max-height: calc(100dvh - 64px);
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #cbd5e1;
  background: #0f172a;
}

.fall-overlay__snapshot img {
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: contain;
  display: block;
}

.fall-overlay__snapshot-empty {
  height: 100%;
  min-height: 240px;
  display: grid;
  place-items: center;
  padding: 16px;
  text-align: center;
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
