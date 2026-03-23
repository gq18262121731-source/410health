<script setup lang="ts">
import { computed, ref, toRef, watch } from "vue";
import type { DeviceBindLogRecord, SessionUser } from "../api/client";
import { ApiError, api } from "../api/client";
import PageHeader from "../components/layout/PageHeader.vue";
import { useCareDirectoryDashboard } from "../composables/useCareDirectoryDashboard";
import { useRelationActions } from "../composables/useRelationActions";

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

const deviceModes = ["register", "bind", "rebind", "unbind"] as const;
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

const {
  deviceForm,
  elderForm,
  familyForm,
  relationBusy,
  relationError,
  relationForm,
  relationStatus,
  submitDeviceAction,
  submitElderRegistration,
  submitFamilyRegistration,
  submitRelationBinding,
} = useRelationActions({
  sessionUser,
  refreshDashboardData,
  getToken: sessionToken,
});

function sessionToken() {
  return localStorage.getItem("ai_health_demo_session_token") ?? "";
}

function formatUiError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
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

function relationFamiliesText(ids: string[]) {
  return ids
    .map((id) => allFamilies.value.find((family) => family.id === id)?.name)
    .filter(Boolean)
    .join(" / ");
}

watch(
  elders,
  (list) => {
    if (!list.length) return;
    if (!relationForm.value.elderUserId) relationForm.value.elderUserId = list[0].id;
    if (!deviceForm.value.targetUserId) deviceForm.value.targetUserId = list[0].id;
  },
  { immediate: true },
);

watch(
  allFamilies,
  (list) => {
    if (list.length && !relationForm.value.familyUserId) {
      relationForm.value.familyUserId = list[0].id;
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
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Member & Device"
      title="成员与设备"
      description="页面级头部只负责展示当前社区、成员规模和同步状态，具体注册、绑定、删除与历史都在页面内部处理。"
      :meta="pageMeta"
    />

    <p v-if="dashboardLoadError" class="feedback-banner feedback-error">{{ dashboardLoadError }}</p>

    <section class="panel-grid relation-grid">
      <article class="panel relation-intro member-device-hero">
        <p class="section-eyebrow">Operation Guide</p>
        <h2>当前操作顺序</h2>
        <p class="subtle-copy">
          本页承接成员注册、家属关系绑定和设备归属操作。页面状态已经下沉，所有局部反馈、历史记录和删除结果都在本页内部处理。
        </p>
        <ul class="rule-list">
          <li data-step="1">先注册老人和家属账号，再建立家属关系。</li>
          <li data-step="2">完成关系绑定后，再为老人注册或绑定设备。</li>
          <li data-step="3">换绑、解绑和删除设备都在同一页面完成，便于统一核对。</li>
          <li data-step="4">设备绑定历史独立展示，方便复查设备归属变更。</li>
        </ul>
        <div v-if="relationStatus" class="status-banner status-success">{{ relationStatus }}</div>
        <div v-if="relationError" class="status-banner status-error">{{ relationError }}</div>
      </article>

      <article class="panel relation-action-card operator-card">
        <p class="section-eyebrow">Member Registration</p>
        <h2>1. 注册老人</h2>
        <div class="form-grid">
          <label class="form-field"><span>姓名</span><input v-model="elderForm.name" class="text-input" type="text" placeholder="请输入老人姓名" /></label>
          <label class="form-field"><span>手机号</span><input v-model="elderForm.phone" class="text-input" type="text" placeholder="请输入手机号" /></label>
          <label class="form-field"><span>年龄</span><input v-model="elderForm.age" class="text-input" type="number" min="1" /></label>
          <label class="form-field"><span>房间号</span><input v-model="elderForm.apartment" class="text-input" type="text" placeholder="例如 A-302" /></label>
          <label class="form-field relation-span-2"><span>初始密码</span><input v-model="elderForm.password" class="text-input" type="text" /></label>
        </div>
        <button type="button" class="primary-btn" :disabled="relationBusy === 'elder'" @click="submitElderRegistration">
          {{ relationBusy === "elder" ? "提交中..." : "注册老人" }}
        </button>
      </article>

      <article class="panel relation-action-card operator-card">
        <p class="section-eyebrow">Family Registration</p>
        <h2>2. 注册家属</h2>
        <div class="form-grid">
          <label class="form-field"><span>姓名</span><input v-model="familyForm.name" class="text-input" type="text" placeholder="请输入家属姓名" /></label>
          <label class="form-field"><span>手机号</span><input v-model="familyForm.phone" class="text-input" type="text" placeholder="请输入手机号" /></label>
          <label class="form-field">
            <span>关系</span>
            <select v-model="familyForm.relationship" class="inline-select relation-select">
              <option value="daughter">女儿</option>
              <option value="son">儿子</option>
              <option value="spouse">配偶</option>
              <option value="granddaughter">孙女</option>
              <option value="grandson">孙子</option>
              <option value="relative">亲属</option>
            </select>
          </label>
          <label class="form-field"><span>登录账号</span><input v-model="familyForm.loginUsername" class="text-input" type="text" placeholder="留空则自动生成" /></label>
          <label class="form-field relation-span-2"><span>初始密码</span><input v-model="familyForm.password" class="text-input" type="text" /></label>
        </div>
        <button type="button" class="primary-btn" :disabled="relationBusy === 'family'" @click="submitFamilyRegistration">
          {{ relationBusy === "family" ? "提交中..." : "注册家属" }}
        </button>
      </article>

      <article class="panel relation-action-card operator-card">
        <p class="section-eyebrow">Relation Binding</p>
        <h2>3. 绑定家属关系</h2>
        <div class="form-grid">
          <label class="form-field">
            <span>老人</span>
            <select v-model="relationForm.elderUserId" class="inline-select relation-select">
              <option v-for="elder in elders" :key="elder.id" :value="elder.id">{{ elder.name }} / {{ elder.apartment }}</option>
            </select>
          </label>
          <label class="form-field">
            <span>家属</span>
            <select v-model="relationForm.familyUserId" class="inline-select relation-select">
              <option v-for="family in allFamilies" :key="family.id" :value="family.id">{{ family.name }} / {{ family.relationship }}</option>
            </select>
          </label>
          <label class="form-field">
            <span>关系类型</span>
            <select v-model="relationForm.relationType" class="inline-select relation-select">
              <option value="daughter">女儿</option>
              <option value="son">儿子</option>
              <option value="spouse">配偶</option>
              <option value="granddaughter">孙女</option>
              <option value="grandson">孙子</option>
              <option value="relative">亲属</option>
            </select>
          </label>
          <label class="form-field checkbox-field"><input v-model="relationForm.isPrimary" type="checkbox" /><span>设为主家属</span></label>
        </div>
        <button type="button" class="primary-btn" :disabled="relationBusy === 'relation'" @click="submitRelationBinding">
          {{ relationBusy === "relation" ? "提交中..." : "绑定关系" }}
        </button>
      </article>

      <article class="panel relation-action-card operator-card">
        <p class="section-eyebrow">Device Ownership</p>
        <h2>4. 管理设备归属</h2>
        <div class="mode-switch">
          <button
            v-for="mode in deviceModes"
            :key="mode"
            type="button"
            class="switch-btn mini-switch"
            :class="{ active: deviceForm.mode === mode }"
            @click="deviceForm.mode = mode"
          >
            {{ mode === "register" ? "注册设备" : mode === "bind" ? "绑定设备" : mode === "rebind" ? "换绑设备" : "解绑设备" }}
          </button>
        </div>
        <div class="form-grid">
          <label class="form-field">
            <span>设备 MAC</span>
            <input v-if="deviceForm.mode === 'register'" v-model="deviceForm.macAddress" class="text-input" type="text" placeholder="请输入设备 MAC" />
            <select v-else v-model="deviceForm.macAddress" class="inline-select relation-select">
              <option v-for="device in devices" :key="device.mac_address" :value="device.mac_address">
                {{ device.device_name }} / {{ device.mac_address }}
              </option>
            </select>
          </label>
          <label v-if="deviceForm.mode === 'register'" class="form-field"><span>设备名称</span><input v-model="deviceForm.deviceName" class="text-input" type="text" placeholder="请输入设备名称" /></label>
          <label v-if="deviceForm.mode !== 'unbind'" class="form-field">
            <span>目标老人</span>
            <select v-model="deviceForm.targetUserId" class="inline-select relation-select">
              <option v-for="elder in elders" :key="elder.id" :value="elder.id">{{ elder.name }} / {{ elder.apartment }}</option>
            </select>
          </label>
          <label v-if="deviceForm.mode === 'rebind' || deviceForm.mode === 'unbind'" class="form-field relation-span-2"><span>操作原因</span><input v-model="deviceForm.reason" class="text-input" type="text" placeholder="请输入换绑或解绑原因" /></label>
        </div>
        <button type="button" class="primary-btn" :disabled="relationBusy === 'device'" @click="submitDeviceAction">
          {{ relationBusy === "device" ? "提交中..." : "提交设备操作" }}
        </button>
      </article>

      <article class="panel relation-table dashboard-section-panel">
        <div class="dashboard-section-head">
          <div>
            <p class="section-eyebrow">Member Ledger</p>
            <h2>成员与关系台账</h2>
          </div>
          <span class="meta-pill">展示当前成员绑定结果</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>老人</th>
                <th>设备</th>
                <th>社区</th>
                <th>家属关系</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="elder in elders" :key="elder.id">
                <td>{{ elder.name }}</td>
                <td>{{ elder.device_mac || "未绑定" }}</td>
                <td>{{ community?.name || "-" }}</td>
                <td>{{ relationFamiliesText(elder.family_ids) || "暂无关系" }}</td>
              </tr>
              <tr v-if="!elders.length">
                <td colspan="4">当前社区还没有成员台账数据。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel relation-table dashboard-section-panel">
        <div class="panel-head">
          <div>
            <h2>设备清单</h2>
            <p class="subtle-copy">设备归属与删除操作都在这里完成，同时支持切换下方的绑定历史查看对象。</p>
          </div>
        </div>
        <p v-if="dashboardLoading && !devices.length" class="helper-copy">正在加载设备清单...</p>
        <p v-else-if="lastDeletedDeviceMac" class="helper-copy">最近删除的设备：{{ lastDeletedDeviceMac }}</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>设备</th>
                <th>状态</th>
                <th>绑定状态</th>
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
                <td>{{ device.bind_status ?? "-" }}</td>
                <td>{{ elders.find((elder) => elder.id === device.user_id)?.name ?? "未归属" }}</td>
                <td>
                  <div class="table-actions">
                    <button type="button" class="ghost-btn" @click.stop="deviceHistoryMac = device.mac_address">查看历史</button>
                    <button type="button" class="ghost-btn danger-btn" :disabled="deletingMac === device.mac_address" @click.stop="deleteDeviceRecord(device.mac_address)">
                      {{ deletingMac === device.mac_address ? "删除中..." : "删除设备" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="!devices.length">
                <td colspan="5">当前还没有设备清单。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel relation-table dashboard-section-panel">
        <div class="panel-head">
          <div>
            <h2>绑定历史</h2>
            <p class="subtle-copy">
              {{ selectedHistoryDevice ? `当前查看 ${selectedHistoryDevice.device_name} / ${selectedHistoryDevice.mac_address}` : "请选择一个设备查看绑定历史。" }}
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
                <td colspan="5">{{ deviceHistoryMac ? "当前设备还没有绑定历史。" : "请选择一个设备查看绑定历史。" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>
  </section>
</template>
