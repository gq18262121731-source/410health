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

function fallScore(alarm: AlarmRecord) {
  const score = fallEvent(alarm)?.fall_score;
  return typeof score === "number" ? `${Math.round(score * 100)}%` : "--";
}

function fallLevel(alarm: AlarmRecord) {
  const level = fallInjury(alarm)?.level;
  return typeof level === "string" && level ? level : "待评估";
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
  return typeof path === "string" && path ? api.getCameraFallSnapshotUrl(path) : "";
}
</script>

<template>
  <section class="panel alarm-panel">
    <div class="panel-head">
      <div>
        <h2>活动告警</h2>
        <p class="panel-subtitle">按优先级展示当前仍需跟进的告警，帮助社区值守人员快速完成分诊、联系与闭环。</p>
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
            <span>置信度 {{ fallScore(alarm) }}</span>
            <span>风险 {{ fallSeverity(alarm) }} / {{ fallLevel(alarm) }}</span>
            <span v-if="fallAdvice(alarm)">{{ fallAdvice(alarm) }}</span>
          </div>
          <img
            v-if="isFallAlarm(alarm) && fallSnapshotUrl(alarm)"
            class="fall-alarm-snapshot"
            :src="fallSnapshotUrl(alarm)"
            alt="跌倒告警截图"
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
