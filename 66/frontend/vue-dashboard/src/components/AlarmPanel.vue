<script setup lang="ts">
import { api, type AlarmRecord } from "../api/client";

defineProps<{ alarms: AlarmRecord[] }>();

defineEmits<{
  (event: "ack", alarmId: string): void;
}>();

function alarmTone(level: number) {
  if (level <= 1) return "sos";
  if (level === 2) return "critical";
  if (level === 3) return "warning";
  return "notice";
}

function alarmLabel(level: number) {
  if (level <= 1) return "SOS";
  if (level === 2) return "严重";
  if (level === 3) return "预警";
  return "通知";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isFallAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "fall_detected" || alarm.alarm_type === "fall_injury_risk";
}

function fallEvent(alarm: AlarmRecord) {
  return asRecord(alarm.metadata?.event);
}

function fallInjury(alarm: AlarmRecord) {
  return asRecord(fallEvent(alarm)?.injury);
}

function fallReview(alarm: AlarmRecord) {
  return asRecord(fallEvent(alarm)?.multimodal_review);
}

function fallScore(alarm: AlarmRecord) {
  const score = fallEvent(alarm)?.fall_score;
  return typeof score === "number" ? `${Math.round(score * 100)}%` : "--";
}

function fallLevel(alarm: AlarmRecord) {
  const level = fallInjury(alarm)?.level;
  return typeof level === "string" && level ? level : "Pending";
}

function fallSeverity(alarm: AlarmRecord) {
  const severity = fallEvent(alarm)?.severity;
  return typeof severity === "string" && severity ? severity : "L?";
}

function fallAdvice(alarm: AlarmRecord) {
  const advice = fallInjury(alarm)?.advice;
  return typeof advice === "string" && advice ? advice : "";
}

function fallSnapshotUrl(alarm: AlarmRecord) {
  const path = fallEvent(alarm)?.snapshot_path;
  const directUrl = fallEvent(alarm)?.snapshot_url;
  const value = typeof directUrl === "string" && directUrl ? directUrl : path;
  return typeof value === "string" && value ? api.getCameraFallSnapshotUrl(value) : "";
}

function fallReviewLabel(alarm: AlarmRecord) {
  const review = fallReview(alarm);
  const judgement = review?.judgement;
  const confidence = typeof review?.confidence === "string" ? review.confidence : "";
  const action = typeof review?.recommended_action === "string" ? review.recommended_action : "";
  switch (judgement) {
    case "fall":
      return "Second review keeps alert";
    case "possible_fall":
      return "Second review suggests manual review";
    case "no_fall":
      return confidence === "medium" || confidence === "high" || action === "downgrade"
        ? "Second review leans false alarm"
        : "Second review leans false alarm with low confidence";
    case "uncertain":
      return "Second review is inconclusive";
    default:
      return "";
  }
}

function fallReviewTone(alarm: AlarmRecord) {
  const review = fallReview(alarm);
  const judgement = review?.judgement;
  const confidence = typeof review?.confidence === "string" ? review.confidence : "";
  const action = typeof review?.recommended_action === "string" ? review.recommended_action : "";
  switch (judgement) {
    case "fall":
      return "keep";
    case "possible_fall":
      return "review";
    case "no_fall":
      return confidence === "medium" || confidence === "high" || action === "downgrade" ? "downgrade" : "neutral";
    default:
      return "neutral";
  }
}

function fallReviewMeta(alarm: AlarmRecord) {
  const review = fallReview(alarm);
  const parts: string[] = [];
  const confidence = review?.confidence;
  const action = review?.recommended_action;
  if (typeof confidence === "string" && confidence) parts.push(`Confidence ${confidence}`);
  if (typeof action === "string" && action) parts.push(`Action ${action}`);
  return parts.join(" · ");
}

function fallReviewReason(alarm: AlarmRecord) {
  const reason = fallReview(alarm)?.reason;
  return typeof reason === "string" && reason ? reason : "";
}
</script>

<template>
  <section class="panel alarm-panel">
    <div class="panel-head">
      <div>
        <h2>活动告警</h2>
        <p class="panel-subtitle">
          按优先级展示当前仍需跟进的告警，帮助值守人员快速完成分诊、联系与闭环。
        </p>
      </div>
      <span>{{ alarms.length }} 条</span>
    </div>

    <div class="alarm-list">
      <article
        v-for="alarm in alarms"
        :key="alarm.id"
        class="alarm-card"
        :class="`alarm-${alarmTone(alarm.alarm_level)}`"
      >
        <div class="alarm-copy">
          <div class="alarm-title-row">
            <p>{{ alarm.device_mac }}</p>
            <span class="alarm-tag">{{ alarmLabel(alarm.alarm_level) }}</span>
          </div>
          <strong>{{ alarm.message }}</strong>
          <div v-if="isFallAlarm(alarm)" class="fall-alarm-detail">
            <span>Score {{ fallScore(alarm) }}</span>
            <span>Risk {{ fallSeverity(alarm) }} / {{ fallLevel(alarm) }}</span>
            <span v-if="fallAdvice(alarm)">{{ fallAdvice(alarm) }}</span>
          </div>
          <div
            v-if="isFallAlarm(alarm) && fallReviewLabel(alarm)"
            class="fall-review-chip"
            :class="`fall-review-chip--${fallReviewTone(alarm)}`"
          >
            <strong>{{ fallReviewLabel(alarm) }}</strong>
            <span v-if="fallReviewMeta(alarm)">{{ fallReviewMeta(alarm) }}</span>
            <small v-if="fallReviewReason(alarm)">{{ fallReviewReason(alarm) }}</small>
          </div>
          <img
            v-if="isFallAlarm(alarm) && fallSnapshotUrl(alarm)"
            class="fall-alarm-snapshot"
            :src="fallSnapshotUrl(alarm)"
            alt="fall snapshot"
          />
          <small>{{ new Date(alarm.created_at).toLocaleString("zh-CN", { hour12: false }) }}</small>
        </div>
        <div class="alarm-actions">
          <span>优先级 {{ alarm.alarm_level }}</span>
          <button @click="$emit('ack', alarm.id)">标记已处理</button>
        </div>
      </article>
      <p v-if="!alarms.length" class="empty-copy">当前没有活动告警，系统运行状态平稳。</p>
    </div>
  </section>
</template>

<style scoped>
.alarm-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.alarm-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: start;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
}

.alarm-card.alarm-sos,
.alarm-card.alarm-critical {
  border-color: rgba(239, 68, 68, 0.3);
  box-shadow: inset 3px 0 0 rgba(239, 68, 68, 0.84);
}

.alarm-card.alarm-warning {
  border-color: rgba(245, 158, 11, 0.34);
  box-shadow: inset 3px 0 0 rgba(245, 158, 11, 0.84);
}

.alarm-copy {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.alarm-title-row,
.alarm-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.alarm-title-row {
  justify-content: space-between;
}

.alarm-title-row p,
.alarm-copy small,
.alarm-actions span,
.empty-copy {
  margin: 0;
  color: var(--text-sub);
}

.alarm-tag {
  border-radius: 999px;
  padding: 3px 9px;
  background: rgba(239, 68, 68, 0.1);
  color: #b42318;
  font-size: 0.78rem;
  font-weight: 800;
}

.fall-alarm-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fall-alarm-detail span {
  border-radius: 999px;
  padding: 4px 9px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 0.78rem;
  font-weight: 700;
}

.fall-alarm-snapshot {
  width: min(280px, 100%);
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  border: 1px solid #dbe4f0;
  object-fit: cover;
  background: #0f172a;
}

.fall-review-chip {
  display: grid;
  gap: 4px;
  max-width: 520px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #dbe4f0;
  background: #ffffff;
}

.fall-review-chip--keep {
  border-color: rgba(180, 35, 24, 0.24);
  background: rgba(254, 242, 242, 0.72);
}

.fall-review-chip--review {
  border-color: rgba(245, 158, 11, 0.26);
  background: rgba(255, 251, 235, 0.92);
}

.fall-review-chip--downgrade {
  border-color: rgba(8, 145, 178, 0.22);
  background: rgba(240, 249, 255, 0.92);
}

.fall-review-chip strong,
.fall-review-chip span,
.fall-review-chip small {
  color: #334155;
  line-height: 1.5;
}

.fall-review-chip small {
  color: #475569;
}

.alarm-actions {
  flex-direction: column;
  align-items: flex-end;
}

.alarm-actions button {
  border: none;
  border-radius: 999px;
  padding: 8px 13px;
  background: var(--brand);
  color: #fff;
  font-weight: 800;
  cursor: pointer;
}

@media (max-width: 720px) {
  .alarm-card {
    grid-template-columns: 1fr;
  }

  .alarm-actions {
    align-items: stretch;
  }
}
</style>
