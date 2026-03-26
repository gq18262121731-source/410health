<script setup lang="ts">
import { computed, onMounted, ref, toRef, watch } from "vue";
import type { DeviceBindLogRecord, SessionUser, SystemInfoResponse } from "../api/client";
import { ApiError, api } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCareDirectoryDashboard } from "../composables/useCareDirectoryDashboard";
import { useRelationActions } from "../composables/useRelationActions";
import { SELECTED_DEVICE_STORAGE_KEY } from "../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
}>();

const sessionUser = toRef(props, "sessionUser");
const {
  allFamilies,
  community,
  dashboardLoadError,
  dashboardLoading,
  devices,
  elders,
  lastSyncAt,
  refreshDashboardData,
} = useCareDirectoryDashboard(sessionUser, {
  includeAllDevices: true,
  pollIntervalMs: 15000,
});

const deviceHistoryMac = ref("");
const bindHistory = ref<DeviceBindLogRecord[]>([]);
const bindHistoryLoading = ref(false);
const bindHistoryError = ref("");
const deletingMac = ref("");
const lastDeletedDeviceMac = ref("");
const systemInfo = ref<SystemInfoResponse | null>(null);
const systemInfoError = ref("");

const unbindingMac = ref("");
const unbindError = ref("");
const unbindReason = ref("");

const {
  deviceForm,
  elderForm,
  lastRegisteredDeviceMac,
  relationBusy,
  relationError,
  relationStatus,
  submitDeviceAction,
  submitElderRegistration,
} = useRelationActions({
  sessionUser,
  refreshDashboardData,
  getToken: sessionToken,
});

function sessionToken() {
  return localStorage.getItem("ai_health_demo_session_token") ?? "";
}

async function unbindDeviceRecord(mac: string) {
  unbindingMac.value = mac;
  unbindError.value = "";
  deviceForm.value.mode = "unbind";
  deviceForm.value.macAddress = mac;
  deviceForm.value.reason = unbindReason.value;
  await submitDeviceAction();
  unbindReason.value = "";
  unbindingMac.value = "";
  deviceForm.value.mode = "register";
}

function formatUiError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function describeBootstrapReason(reason: string | undefined) {
  if (!reason) return "采集器暂未接入";
  if (reason === "shouhuan_missing") return "等待采集器接入";
  if (reason.startsWith("shouhuan_parse_failed")) return "采集配置待检查";
  if (reason === "pyserial_missing") return "采集组件未就绪";
  if (reason.startsWith("serial_open_failed")) return "采集器暂未连接";
  if (reason === "serial_port_available") return "采集器已就绪";
  return "采集器状态待确认";
}

const syncLabel = computed(() =>
  lastSyncAt.value ? lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false }) : "尚未同步",
);
const pageMeta = computed(() => [
  `社区 ${community.value?.name || "未分配"}`,
  `老人 ${elders.value.length}`,
  `家属 ${allFamilies.value.length}`,
  `设备 ${devices.value.length}`,
  `同步 ${syncLabel.value}`,
]);
const selectedHistoryDevice = computed(
  () => devices.value.find((device) => device.mac_address === deviceHistoryMac.value) ?? null,
);
const serialRuntime = computed(() => systemInfo.value?.serial_runtime ?? null);
const runtimeMode = computed(() => systemInfo.value?.runtime_mode ?? serialRuntime.value?.runtime_mode ?? "mock");
const serialRuntimeSummary = computed(() => {
  const runtime = serialRuntime.value;
  if (!runtime) return "当前未读取到串口采集配置。";
  const collectionStrategy = runtime.collection_strategy ?? "single_target";
  const targetLabel = runtime.active_target_mac ?? "未锁定目标";
  if (runtimeMode.value === "serial") {
    return `串口已启用 · ${runtime.port} · ${runtime.baudrate} baud · ${collectionStrategy} · ${targetLabel}`;
  }
  const fallbackReason = describeBootstrapReason(runtime.bootstrap_reason ?? systemInfo.value?.bootstrap_reason);
  return `社区样本链路 · ${fallbackReason}`;
});
const collectorPortLabel = computed(() => {
  if (runtimeMode.value !== "serial") return "待识别";
  return serialRuntime.value?.port || "auto-detect";
});
const collectorStatusLabel = computed(() => {
  if (runtimeMode.value === "serial") return "串口已启用，等待完整 A/B 双包";
  return `${describeBootstrapReason(serialRuntime.value?.bootstrap_reason ?? systemInfo.value?.bootstrap_reason)}，可先完成台账登记`;
});
const activeTargetLabel = computed(() => {
  if (runtimeMode.value !== "serial") return "采集器接入后自动锁定";
  const runtime = serialRuntime.value;
  if (!runtime?.active_target_mac) return "未锁定";
  return runtime.active_target_device_name
    ? `${runtime.active_target_device_name} / ${runtime.active_target_mac}`
    : runtime.active_target_mac;
});
const packetMergeLabel = computed(() =>
  serialRuntime.value?.merge_mode === "wait_for_ab" ? "等待 A+B 完整双包" : "未识别",
);
const macInputExamples = computed(() => ["5410260100DF", "54:10:26:01:00:DF"]);
const pendingDeviceCount = computed(() => devices.value.filter((device) => device.status === "pending").length);
const hasElders = computed(() => elders.value.length > 0);
const selectedTargetElder = computed(
  () => elders.value.find((elder) => elder.id === deviceForm.value.targetUserId) ?? null,
);
const lastRegisteredDevice = computed(
  () => devices.value.find((device) => device.mac_address === lastRegisteredDeviceMac.value) ?? null,
);

async function loadSystemInfo() {
  systemInfoError.value = "";
  try {
    systemInfo.value = await api.getSystemInfo();
  } catch (error) {
    systemInfo.value = null;
    systemInfoError.value = formatUiError(error, "系统运行配置读取失败，请稍后重试。");
  }
}

async function refreshBindHistory(mac: string) {
  bindHistoryLoading.value = true;
  bindHistoryError.value = "";
  try {
    bindHistory.value = await api.listDeviceBindLogs(mac);
  } catch (error) {
    bindHistory.value = [];
    bindHistoryError.value = formatUiError(error, "绑定历史加载失败，请稍后重试。");
  } finally {
    bindHistoryLoading.value = false;
  }
}

async function deleteDeviceRecord(mac: string) {
  deletingMac.value = mac;
  try {
    await api.deleteDevice(mac, sessionToken());
    lastDeletedDeviceMac.value = mac;
    await refreshDashboardData();
    await loadSystemInfo();
    if (deviceHistoryMac.value === mac) {
      deviceHistoryMac.value = "";
      bindHistory.value = [];
    }
  } catch (error) {
    bindHistoryError.value = formatUiError(error, "设备删除失败，请稍后重试。");
  } finally {
    deletingMac.value = "";
  }
}

function goToOverviewForRegisteredDevice() {
  if (!lastRegisteredDeviceMac.value) return;
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(SELECTED_DEVICE_STORAGE_KEY, lastRegisteredDeviceMac.value);
    window.location.hash = "#/overview";
  }
}

function dismissRegisteredDevicePrompt() {
  lastRegisteredDeviceMac.value = "";
}

function submitPrimaryRegisterAction() {
  deviceForm.value.mode = "register";
  void submitDeviceAction();
}

watch(
  elders,
  (list) => {
    if (!list.length) {
      deviceForm.value.targetUserId = "";
      return;
    }
    if (deviceForm.value.targetUserId && !list.some((elder) => elder.id === deviceForm.value.targetUserId)) {
      deviceForm.value.targetUserId = "";
    }
  },
  { immediate: true },
);

watch(
  devices,
  (list) => {
    if (!list.length) {
      deviceHistoryMac.value = "";
      bindHistory.value = [];
      bindHistoryError.value = "";
      return;
    }

    if (!list.some((item) => item.mac_address === deviceHistoryMac.value)) {
      deviceHistoryMac.value = list[0].mac_address;
      return;
    }

    if (deviceHistoryMac.value) void refreshBindHistory(deviceHistoryMac.value);
  },
  { immediate: true },
);

watch(deviceHistoryMac, (mac) => {
  if (!mac) {
    bindHistory.value = [];
    bindHistoryError.value = "";
    return;
  }
  void refreshBindHistory(mac);
});

watch(lastRegisteredDeviceMac, (mac) => {
  if (mac) void loadSystemInfo();
});

onMounted(() => {
  deviceForm.value.mode = "register";
  void loadSystemInfo();
});
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Member & Device"
      title="成员设备"
      description="先登记真实 T10 手环，可选择立即绑定老人，也可以先空挂设备台账；采集器收到完整 A/B 双包后，设备会从 pending 自动切到在线监控。"
      :meta="pageMeta"
    />

    <p v-if="dashboardLoadError" class="feedback-banner feedback-error">{{ dashboardLoadError }}</p>

    <section class="member-device-grid">
      <article class="panel member-device-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">T10 Device Onboarding</p>
            <h2>注册真实 T10 手环</h2>
            <p class="subtle-copy">
              运营人员只需要输入手环 MAC。你可以直接绑定老人，也可以先登记到设备台账，后续再补绑定关系。
            </p>
          </div>
          <div class="badge-row">
            <span class="summary-badge">{{ serialRuntimeSummary }}</span>
            <span class="summary-badge">待激活设备 {{ pendingDeviceCount }}</span>
            <span v-if="selectedTargetElder" class="summary-badge">默认老人 {{ selectedTargetElder.name }}</span>
          </div>
        </div>

        <div class="form-grid">
          <label class="form-field">
            <span>设备 MAC</span>
            <input
              v-model="deviceForm.macAddress"
              class="text-input"
              type="text"
              placeholder="例如 5410260100DF 或 54:10:26:01:00:DF"
            />
          </label>
          <label class="form-field">
            <span>目标老人（可选）</span>
            <select v-model="deviceForm.targetUserId" class="inline-select relation-select" :disabled="!hasElders">
              <option value="">暂不绑定，先登记设备</option>
              <option v-for="elder in elders" :key="elder.id" :value="elder.id">{{ elder.name }} / {{ elder.apartment }}</option>
            </select>
          </label>
        </div>

        <div class="readout-grid">
          <div class="readout-card">
            <span>采集器串口</span>
            <strong>{{ collectorPortLabel }}</strong>
          </div>
          <div class="readout-card">
            <span>串口状态</span>
            <strong>{{ collectorStatusLabel }}</strong>
          </div>
          <div class="readout-card">
            <span>当前采集目标</span>
            <strong>{{ activeTargetLabel }}</strong>
          </div>
          <div class="readout-card">
            <span>合并模式</span>
            <strong>{{ packetMergeLabel }}</strong>
          </div>
          <div class="readout-card">
            <span>设备名称</span>
            <strong>{{ deviceForm.deviceName }}</strong>
          </div>
          <div class="readout-card">
            <span>型号编码</span>
            <strong>{{ deviceForm.modelCode }}</strong>
          </div>
          <div class="readout-card">
            <span>接入方式</span>
            <strong>{{ deviceForm.ingestMode }}</strong>
          </div>
          <div class="readout-card wide">
            <span>服务 UUID</span>
            <strong>{{ deviceForm.serviceUuid }}</strong>
          </div>
          <div class="readout-card wide">
            <span>设备 UUID</span>
            <strong>{{ deviceForm.deviceUuid }}</strong>
          </div>
          <div class="readout-card wide">
            <span>MAC 输入格式</span>
            <strong>{{ macInputExamples.join(" / ") }}</strong>
          </div>
        </div>

        <div class="tips-block">
          <strong>接入说明</strong>
          <p>
            当前串口链路对齐 `shouhuan.py`：采集器锁定一个目标 MAC，并等待两个响应包都到达。只有 A/B 双包合并成功后，系统才会推送实时心率、血氧、血压和体温。
          </p>
        </div>

        <div class="action-row">
          <button
            type="button"
            class="primary-btn"
            :disabled="relationBusy === 'device'"
            @click="submitPrimaryRegisterAction"
          >
            {{ relationBusy === "device" ? "正在注册..." : "注册手环并等待接入" }}
          </button>
          <p class="helper-copy">
            注册成功后设备会先显示为 <code>pending</code>。可以先空挂到设备台账，后续再补绑定；真实串口接入后，采集器收到完整 A/B 双包就会刷新实时面板。
          </p>
        </div>

        <p v-if="systemInfoError" class="error-copy">{{ systemInfoError }}</p>
        <div v-if="relationStatus" class="status-banner status-success">{{ relationStatus }}</div>
        <div v-if="unbindError" class="status-banner status-error">{{ unbindError }}</div>
        <div v-if="relationError" class="status-banner status-error">{{ relationError }}</div>

        <div v-if="lastRegisteredDeviceMac" class="register-prompt">
          <div>
            <strong>{{ lastRegisteredDevice?.device_name ?? "T10-WATCH" }} 已注册</strong>
            <p>
              {{ lastRegisteredDeviceMac }} 已进入设备台账，当前状态为 {{ lastRegisteredDevice?.status ?? "pending" }}。
              {{ lastRegisteredDevice?.user_id ? "该设备已写入成员关系。" : "该设备当前处于未归属状态，后续可再补绑定。" }}
              采集器接入后，这台设备会被自动锁定为当前采集目标，待完整 A/B 双包到达后即可进入实时监控。
            </p>
          </div>
          <div class="table-actions">
            <button type="button" class="primary-btn" @click="goToOverviewForRegisteredDevice">前往总览监控</button>
            <button type="button" class="ghost-btn" @click="dismissRegisteredDevicePrompt">留在当前页面</button>
          </div>
        </div>
      </article>

      <article class="panel member-device-panel" v-if="!hasElders">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Elder Registration</p>
            <h2>先补一位老人账号</h2>
            <p class="subtle-copy">如果当前社区还没有老人资料，可以先在这里补一位老人，再回来绑定手环。</p>
          </div>
        </div>

        <div class="form-grid">
          <label class="form-field">
            <span>姓名</span>
            <input v-model="elderForm.name" class="text-input" type="text" placeholder="请输入老人姓名" />
          </label>
          <label class="form-field">
            <span>手机号</span>
            <input v-model="elderForm.phone" class="text-input" type="text" placeholder="请输入手机号" />
          </label>
          <label class="form-field">
            <span>年龄</span>
            <input v-model="elderForm.age" class="text-input" type="number" min="1" />
          </label>
          <label class="form-field">
            <span>房间</span>
            <input v-model="elderForm.apartment" class="text-input" type="text" placeholder="例如 A-302" />
          </label>
        </div>

        <div class="action-row">
          <button type="button" class="primary-btn" :disabled="relationBusy === 'elder'" @click="submitElderRegistration">
            {{ relationBusy === "elder" ? "正在提交..." : "登记老人" }}
          </button>
        </div>
      </article>

      <article class="panel member-device-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Device Ledger</p>
            <h2>设备清单</h2>
            <p class="subtle-copy">新注册的 T10 会先以 pending 展示；收到完整双包后自动变为 online。</p>
          </div>
          <span v-if="lastDeletedDeviceMac" class="meta-pill">最近删除 {{ lastDeletedDeviceMac }}</span>
        </div>

        <p v-if="dashboardLoading && !devices.length" class="helper-copy">正在加载设备清单...</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>设备</th>
                <th>状态</th>
                <th>激活</th>
                <th>绑定</th>
                <th>当前归属</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="device in devices"
                :key="device.mac_address"
                :class="{ current: device.mac_address === deviceHistoryMac }"
                @click="deviceHistoryMac = device.mac_address"
              >
                <td>
                  <strong>{{ device.device_name }}</strong>
                  <small>{{ device.mac_address }}</small>
                </td>
                <td>{{ device.status }}</td>
                <td>{{ device.activation_state ?? "-" }}</td>
                <td>{{ device.bind_status ?? "-" }}</td>
                <td>{{ elders.find((elder) => elder.id === device.user_id)?.name ?? "未归属" }}</td>
                <td>
                  <div class="table-actions">
                    <button type="button" class="ghost-btn" @click.stop="deviceHistoryMac = device.mac_address">查看历史</button>
                    <button
                      v-if="device.bind_status === 'bound'"
                      type="button"
                      class="ghost-btn"
                      :disabled="unbindingMac === device.mac_address || relationBusy === 'device'"
                      @click.stop="unbindDeviceRecord(device.mac_address)"
                    >
                      {{ unbindingMac === device.mac_address ? "解绑中..." : "解绑设备" }}
                    </button>
                    <button
                      type="button"
                      class="ghost-btn danger-btn"
                      :disabled="deletingMac === device.mac_address"
                      @click.stop="deleteDeviceRecord(device.mac_address)"
                    >
                      {{ deletingMac === device.mac_address ? "删除中..." : "删除设备" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="!devices.length">
                <td colspan="6">当前还没有设备清单。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel member-device-panel">
        <div class="panel-head">
          <div>
            <p class="section-eyebrow">Bind Timeline</p>
            <h2>绑定历史</h2>
            <p class="subtle-copy">
              {{
                selectedHistoryDevice
                  ? `当前查看 ${selectedHistoryDevice.device_name} / ${selectedHistoryDevice.mac_address}`
                  : "请选择一台设备查看绑定历史。"
              }}
            </p>
          </div>
        </div>

        <p v-if="bindHistoryError" class="error-copy">{{ bindHistoryError }}</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作</th>
                <th>原对象</th>
                <th>新对象</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="bindHistoryLoading">
                <td colspan="5">绑定历史加载中...</td>
              </tr>
              <tr v-for="item in bindHistory" :key="item.id">
                <td>{{ new Date(item.created_at).toLocaleString("zh-CN", { hour12: false }) }}</td>
                <td>{{ item.action_type }}</td>
                <td>{{ item.old_user_id ?? "-" }}</td>
                <td>{{ item.new_user_id ?? "-" }}</td>
                <td>{{ item.reason ?? "-" }}</td>
              </tr>
              <tr v-if="!bindHistoryLoading && !bindHistory.length">
                <td colspan="5">{{ deviceHistoryMac ? "当前设备还没有绑定历史。" : "请选择一台设备查看绑定历史。" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.member-device-grid {
  display: grid;
  gap: 18px;
}

.member-device-panel {
  display: grid;
  gap: 18px;
}

.panel-head,
.badge-row,
.action-row,
.table-actions {
  display: flex;
  gap: 12px;
}

.panel-head {
  justify-content: space-between;
  align-items: flex-start;
}

.panel-head h2 {
  margin: 0;
  color: var(--text-main);
  font-family: var(--font-display);
}

.badge-row {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.form-grid,
.readout-grid {
  display: grid;
  gap: 14px;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.readout-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.readout-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(12, 20, 34, 0.88);
  border: 1px solid rgba(56, 189, 248, 0.10);
}

.readout-card.wide {
  grid-column: span 2;
}

.readout-card span {
  color: var(--text-sub);
  font-size: 0.8rem;
}

.readout-card strong {
  color: var(--text-main);
  word-break: break-all;
}

.tips-block,
.register-prompt {
  padding: 16px 18px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.12), transparent 34%),
    rgba(13, 24, 38, 0.92);
  border: 1px solid rgba(56, 189, 248, 0.12);
  color: var(--text-sub);
}

.tips-block p,
.register-prompt p {
  margin: 8px 0 0;
  line-height: 1.7;
}

.tips-block strong,
.register-prompt strong {
  color: var(--text-main);
}

.action-row {
  align-items: center;
  flex-wrap: wrap;
}

.helper-copy,
.subtle-copy,
.meta-pill {
  color: var(--text-sub);
}

.table-wrap small {
  display: block;
  margin-top: 4px;
  color: var(--text-sub);
}

@media (max-width: 960px) {
  .form-grid,
  .readout-grid {
    grid-template-columns: 1fr;
  }

  .readout-card.wide {
    grid-column: span 1;
  }

  .panel-head {
    flex-direction: column;
  }

  .badge-row {
    justify-content: flex-start;
  }
}
</style>
