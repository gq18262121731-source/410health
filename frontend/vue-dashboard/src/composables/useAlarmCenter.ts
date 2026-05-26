import { computed, onMounted, onUnmounted, ref, watch, type ComputedRef, type Ref } from "vue";
import { api, type AlarmRecord, type SessionUser } from "../api/client";
import { getStoredSessionToken } from "./useSessionAuth";

const activeAlarms = ref<AlarmRecord[]>([]);
const sosAlarmQueue = ref<AlarmRecord[]>([]);
const lastRealtimeUpdateAt = ref<number>(0);

let activeConsumers = 0;
let alarmSocket: WebSocket | null = null;
let refreshTimer: number | null = null;
let reconnectTimer: number | null = null;
let reconnectAttempts = 0;
let runtimeSessionKey = "";

function supportsRealtimeAlarmRuntime(user: SessionUser | null): boolean {
  if (!user) return false;
  return user.role === "community" || user.role === "admin" || user.role === "family" || user.role === "elder";
}

function normalizeAlarmQueuePayload(payload: unknown): AlarmRecord[] {
  if (!Array.isArray(payload)) return [];
  return payload
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const nested = (entry as { alarm?: AlarmRecord }).alarm;
      if (nested && typeof nested === "object" && "id" in nested && "alarm_type" in nested) {
        return nested;
      }
      if ("id" in (entry as Record<string, unknown>) && "alarm_type" in (entry as Record<string, unknown>)) {
        return entry as AlarmRecord;
      }
      return null;
    })
    .filter((item): item is AlarmRecord => item !== null);
}

function syncAlarmState(alarms: AlarmRecord[]) {
  activeAlarms.value = alarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  sosAlarmQueue.value = activeAlarms.value
    .filter((alarm) => alarm.alarm_type === "sos")
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
}

function applyAlarm(alarm: AlarmRecord) {
  const next = [...activeAlarms.value];
  const index = next.findIndex((item) => item.id === alarm.id);
  if (alarm.acknowledged) {
    if (index >= 0) next.splice(index, 1);
  } else if (index >= 0) {
    next.splice(index, 1, alarm);
  } else {
    next.push(alarm);
  }
  syncAlarmState(next);
}

function stopRuntime() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (alarmSocket) {
    alarmSocket.onclose = null;
    alarmSocket.close();
  }
  alarmSocket = null;
}

async function refreshAlarmState() {
  const token = getStoredSessionToken();
  const alarms = await api.listAlarms(token).catch(() => [] as AlarmRecord[]);
  syncAlarmState(alarms);
}

function connectAlarmSocket() {
  if (alarmSocket) {
    alarmSocket.onclose = null;
    alarmSocket.close();
  }
  alarmSocket = null;

  const token = getStoredSessionToken();
  if (!token) return;

  alarmSocket = api.alarmSocket(token);
  alarmSocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AlarmRecord | { type?: string; queue?: Array<{ alarm?: AlarmRecord }> };
      if ("type" in payload && payload.type === "alarm_queue") {
        const alarms = normalizeAlarmQueuePayload(payload.queue);
        syncAlarmState(alarms);
      } else {
        applyAlarm(payload as AlarmRecord);
      }
      lastRealtimeUpdateAt.value = Date.now();
    } catch {
      // ignore malformed websocket payloads
    }
  };
  alarmSocket.onopen = () => {
    reconnectAttempts = 0;
  };
  alarmSocket.onclose = () => {
    alarmSocket = null;
    if (activeConsumers <= 0 || !runtimeSessionKey) return;
    const delay = Math.min(500 * (2 ** reconnectAttempts), 5000);
    reconnectAttempts += 1;
    reconnectTimer = window.setTimeout(connectAlarmSocket, delay);
  };
}

function buildRuntimeSessionKey(user: SessionUser | null) {
  const token = getStoredSessionToken();
  if (!user || !supportsRealtimeAlarmRuntime(user) || !token) return "";
  return `${user.id}:${user.role}:${token}`;
}

function startRuntime(user: SessionUser | null) {
  const nextKey = buildRuntimeSessionKey(user);
  runtimeSessionKey = nextKey;
  stopRuntime();
  if (!nextKey) {
    syncAlarmState([]);
    return;
  }
  void refreshAlarmState();
  connectAlarmSocket();
  refreshTimer = window.setInterval(() => {
    void refreshAlarmState();
  }, 60000);
}

export type AlarmCenterState = {
  activeAlarmCount: ComputedRef<number>;
  activeAlarms: Ref<AlarmRecord[]>;
  lastRealtimeUpdateAt: Ref<number>;
  refreshAlarmState: () => Promise<void>;
  sosAlarmQueue: Ref<AlarmRecord[]>;
  supportsRealtime: ComputedRef<boolean>;
};

export function useAlarmCenter(sessionUser: Ref<SessionUser | null>): AlarmCenterState {
  const supportsRealtime = computed(() => supportsRealtimeAlarmRuntime(sessionUser.value));
  const activeAlarmCount = computed(() => activeAlarms.value.length);

  watch(
    () => buildRuntimeSessionKey(sessionUser.value),
    (nextKey) => {
      if (activeConsumers > 0 && nextKey !== runtimeSessionKey) {
        startRuntime(sessionUser.value);
      }
    },
    { immediate: true },
  );

  onMounted(() => {
    activeConsumers += 1;
    if (activeConsumers === 1) {
      startRuntime(sessionUser.value);
    }
  });

  onUnmounted(() => {
    activeConsumers = Math.max(0, activeConsumers - 1);
    if (activeConsumers === 0) {
      runtimeSessionKey = "";
      stopRuntime();
    }
  });

  return {
    activeAlarmCount,
    activeAlarms,
    lastRealtimeUpdateAt,
    refreshAlarmState,
    sosAlarmQueue,
    supportsRealtime,
  };
}
