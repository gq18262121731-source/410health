<script setup lang="ts">
import type { DeviceBindLogRecord, DeviceRecord, ElderProfile, FamilyProfile } from "../api/client";
import type { BusyKey, DeviceActionMode } from "../composables/useRelationActions";

interface ElderFormModel {
  name: string;
  phone: string;
  password: string;
  age: number;
  apartment: string;
}

interface FamilyFormModel {
  name: string;
  phone: string;
  password: string;
  relationship: string;
  loginUsername: string;
}

interface RelationFormModel {
  elderUserId: string;
  familyUserId: string;
  relationType: string;
  isPrimary: boolean;
}

interface DeviceFormModel {
  mode: DeviceActionMode;
  macAddress: string;
  deviceName: string;
  targetUserId: string;
  reason: string;
}

const props = defineProps<{
  elders: ElderProfile[];
  families: FamilyProfile[];
  communityName: string;
  devices: DeviceRecord[];
  elderForm: ElderFormModel;
  familyForm: FamilyFormModel;
  relationForm: RelationFormModel;
  deviceForm: DeviceFormModel;
  relationBusy: BusyKey;
  relationStatus: string;
  relationError: string;
  deviceModes: readonly DeviceActionMode[];
  dashboardLoading: boolean;
  dashboardLoadError: string;
  lastDeletedDeviceMac: string;
  deviceHistoryMac: string;
  selectedHistoryDevice: DeviceRecord | null;
  bindHistory: DeviceBindLogRecord[];
  bindHistoryLoading: boolean;
  bindHistoryError: string;
  deletingMac: string;
}>();

const elderFormModel = props.elderForm;
const familyFormModel = props.familyForm;
const relationFormModel = props.relationForm;
const deviceFormModel = props.deviceForm;

const emit = defineEmits<{
  submitElderRegistration: [];
  submitFamilyRegistration: [];
  submitRelationBinding: [];
  submitDeviceAction: [];
  deleteDevice: [mac: string];
  "update:deviceHistoryMac": [value: string];
}>();

function relationFamiliesText(ids: string[]) {
  return ids
    .map((id) => props.families.find((family) => family.id === id)?.name)
    .filter(Boolean)
    .join(" / ");
}

function selectDeviceHistory(mac: string) {
  emit("update:deviceHistoryMac", mac);
}
</script>

<template>
  <section class="panel-grid relation-grid">
    <article class="panel relation-intro member-device-hero">
      <p class="section-eyebrow">Member & Device</p>
      <h2>成员与设备</h2>
      <p class="subtle-copy">这一页集中承接成员登记、家属关系、设备归属和绑定历史，避免表单和台账信息散落在多个页面里。</p>
      <div class="dashboard-chip-row">
        <span class="meta-pill">老人 {{ elders.length }}</span>
        <span class="meta-pill">家属 {{ families.length }}</span>
        <span class="meta-pill">设备 {{ devices.length }}</span>
      </div>
      <ul class="rule-list">
        <li data-step="1">先登记老人账号，再登记家属账号。</li>
        <li data-step="2">登记完成后，建立老人和家属之间的关系。</li>
        <li data-step="3">最后登记设备并完成归属，或对已登记设备进行绑定、换绑、解绑。</li>
        <li data-step="4">成员与设备页当前只对运营侧开放，不在家属端直接暴露管理操作。</li>
      </ul>
      <div v-if="relationStatus" class="status-banner status-success">{{ relationStatus }}</div>
      <div v-if="relationError" class="status-banner status-error">{{ relationError }}</div>
    </article>

    <article class="panel relation-action-card operator-card">
      <p class="section-eyebrow">Member Registration</p>
      <h2>1. 老人登记</h2>
      <div class="form-grid">
        <label class="form-field"><span>姓名</span><input v-model="elderFormModel.name" class="text-input" type="text" placeholder="请输入老人姓名" /></label>
        <label class="form-field"><span>手机号</span><input v-model="elderFormModel.phone" class="text-input" type="text" placeholder="请输入手机号" /></label>
        <label class="form-field"><span>年龄</span><input v-model="elderFormModel.age" class="text-input" type="number" min="1" /></label>
        <label class="form-field"><span>房间号</span><input v-model="elderFormModel.apartment" class="text-input" type="text" placeholder="例如 A-302" /></label>
        <label class="form-field relation-span-2"><span>初始密码</span><input v-model="elderFormModel.password" class="text-input" type="text" /></label>
      </div>
      <button type="button" class="primary-btn" :disabled="relationBusy === 'elder'" @click="emit('submitElderRegistration')">
        {{ relationBusy === "elder" ? "提交中..." : "登记老人" }}
      </button>
    </article>

    <article class="panel relation-action-card operator-card">
      <p class="section-eyebrow">Family Registration</p>
      <h2>2. 家属登记</h2>
      <div class="form-grid">
        <label class="form-field"><span>姓名</span><input v-model="familyFormModel.name" class="text-input" type="text" placeholder="请输入家属姓名" /></label>
        <label class="form-field"><span>手机号</span><input v-model="familyFormModel.phone" class="text-input" type="text" placeholder="请输入手机号" /></label>
        <label class="form-field">
          <span>关系类型</span>
          <select v-model="familyFormModel.relationship" class="inline-select relation-select">
            <option value="daughter">女儿</option>
            <option value="son">儿子</option>
            <option value="spouse">配偶</option>
            <option value="granddaughter">孙女</option>
            <option value="grandson">孙子</option>
            <option value="relative">其他亲属</option>
          </select>
        </label>
        <label class="form-field"><span>登录账号</span><input v-model="familyFormModel.loginUsername" class="text-input" type="text" placeholder="可选，自定义账号" /></label>
        <label class="form-field relation-span-2"><span>初始密码</span><input v-model="familyFormModel.password" class="text-input" type="text" /></label>
      </div>
      <button type="button" class="primary-btn" :disabled="relationBusy === 'family'" @click="emit('submitFamilyRegistration')">
        {{ relationBusy === "family" ? "提交中..." : "登记家属" }}
      </button>
    </article>

    <article class="panel relation-action-card operator-card">
      <p class="section-eyebrow">Relation Binding</p>
      <h2>3. 关系绑定</h2>
      <div class="form-grid">
        <label class="form-field">
          <span>老人</span>
          <select v-model="relationFormModel.elderUserId" class="inline-select relation-select">
            <option v-for="elder in elders" :key="elder.id" :value="elder.id">{{ elder.name }} / {{ elder.apartment }}</option>
          </select>
        </label>
        <label class="form-field">
          <span>家属</span>
          <select v-model="relationFormModel.familyUserId" class="inline-select relation-select">
            <option v-for="family in families" :key="family.id" :value="family.id">{{ family.name }} / {{ family.relationship }}</option>
          </select>
        </label>
        <label class="form-field">
          <span>关系</span>
          <select v-model="relationFormModel.relationType" class="inline-select relation-select">
            <option value="daughter">女儿</option>
            <option value="son">儿子</option>
            <option value="spouse">配偶</option>
            <option value="granddaughter">孙女</option>
            <option value="grandson">孙子</option>
            <option value="relative">其他亲属</option>
          </select>
        </label>
        <label class="form-field checkbox-field"><input v-model="relationFormModel.isPrimary" type="checkbox" /><span>设为主要联系人</span></label>
      </div>
      <button type="button" class="primary-btn" :disabled="relationBusy === 'relation'" @click="emit('submitRelationBinding')">
        {{ relationBusy === "relation" ? "提交中..." : "建立关系" }}
      </button>
    </article>

    <article class="panel relation-action-card operator-card">
      <p class="section-eyebrow">Device Ownership</p>
      <h2>4. 设备归属</h2>
      <div class="mode-switch">
        <button
          v-for="mode in deviceModes"
          :key="mode"
          type="button"
          class="switch-btn mini-switch"
          :class="{ active: deviceFormModel.mode === mode }"
          @click="deviceFormModel.mode = mode"
        >
          {{ mode === "register" ? "登记并绑定" : mode === "bind" ? "绑定已有设备" : mode === "rebind" ? "换绑" : "解绑" }}
        </button>
      </div>
      <div class="form-grid">
        <label class="form-field">
          <span>设备 MAC</span>
          <input v-if="deviceFormModel.mode === 'register'" v-model="deviceFormModel.macAddress" class="text-input" type="text" placeholder="请输入设备 MAC" />
          <select v-else v-model="deviceFormModel.macAddress" class="inline-select relation-select">
            <option v-for="device in devices" :key="device.mac_address" :value="device.mac_address">{{ device.device_name }} / {{ device.mac_address }}</option>
          </select>
        </label>
        <label v-if="deviceFormModel.mode === 'register'" class="form-field"><span>设备名称</span><input v-model="deviceFormModel.deviceName" class="text-input" type="text" placeholder="请输入设备名称" /></label>
        <label v-if="deviceFormModel.mode !== 'unbind'" class="form-field">
          <span>归属老人</span>
          <select v-model="deviceFormModel.targetUserId" class="inline-select relation-select">
            <option v-for="elder in elders" :key="elder.id" :value="elder.id">{{ elder.name }} / {{ elder.apartment }}</option>
          </select>
        </label>
        <label v-if="deviceFormModel.mode === 'rebind' || deviceFormModel.mode === 'unbind'" class="form-field relation-span-2"><span>原因说明</span><input v-model="deviceFormModel.reason" class="text-input" type="text" placeholder="可选，记录操作原因" /></label>
      </div>
      <button type="button" class="primary-btn" :disabled="relationBusy === 'device'" @click="emit('submitDeviceAction')">
        {{ relationBusy === "device" ? "提交中..." : "提交设备操作" }}
      </button>
    </article>

    <article class="panel relation-table dashboard-section-panel">
      <div class="dashboard-section-head">
        <div>
          <p class="section-eyebrow">Member Ledger</p>
          <h2>当前成员关系</h2>
        </div>
        <span class="meta-pill">成员与设备视角</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>老人</th><th>设备</th><th>社区</th><th>家属关系</th></tr></thead>
          <tbody>
            <tr v-for="elder in elders" :key="elder.id">
              <td>{{ elder.name }}</td>
              <td>{{ elder.device_mac || "未绑定设备" }}</td>
              <td>{{ communityName || "-" }}</td>
              <td>{{ relationFamiliesText(elder.family_ids) || "未建立关系" }}</td>
            </tr>
            <tr v-if="!elders.length">
              <td colspan="4">当前还没有正式登记的老人，请先完成注册。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="panel relation-table dashboard-section-panel">
      <div class="panel-head">
        <div>
          <h2>设备清单</h2>
          <p class="subtle-copy">删除设备后，若要再次绑定，必须先重新注册设备。</p>
        </div>
      </div>
      <p v-if="dashboardLoadError" class="error-copy">{{ dashboardLoadError }}</p>
      <p v-else-if="dashboardLoading && !devices.length" class="helper-copy">设备列表刷新中，请稍候...</p>
      <p v-else-if="lastDeletedDeviceMac" class="helper-copy">最近删除设备：{{ lastDeletedDeviceMac }}。如需再次使用，请先重新注册。</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>设备</th><th>状态</th><th>绑定状态</th><th>当前归属</th><th>操作</th></tr></thead>
          <tbody>
            <tr
              v-for="device in devices"
              :key="device.mac_address"
              :class="{ current: device.mac_address === deviceHistoryMac }"
              @click="selectDeviceHistory(device.mac_address)"
            >
              <td><strong>{{ device.device_name }}</strong><small>{{ device.mac_address }}</small></td>
              <td>{{ device.status }}</td>
              <td>{{ device.bind_status ?? "-" }}</td>
              <td>{{ elders.find((elder) => elder.id === device.user_id)?.name ?? "未绑定老人" }}</td>
              <td>
                <div class="table-actions">
                  <button type="button" class="ghost-btn" @click.stop="selectDeviceHistory(device.mac_address)">查看历史</button>
                  <button type="button" class="ghost-btn danger-btn" :disabled="deletingMac === device.mac_address" @click.stop="emit('deleteDevice', device.mac_address)">
                    {{ deletingMac === device.mac_address ? "删除中..." : "删除设备" }}
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="dashboardLoading && !devices.length">
              <td colspan="5">设备列表加载中...</td>
            </tr>
            <tr v-else-if="!devices.length">
              <td colspan="5">当前没有设备记录。完成设备登记后，这里会显示设备状态与操作入口。</td>
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
            {{ selectedHistoryDevice ? `当前查看：${selectedHistoryDevice.device_name} / ${selectedHistoryDevice.mac_address}` : "请选择一台设备查看绑定历史。" }}
          </p>
        </div>
      </div>
      <p v-if="bindHistoryError" class="error-copy">{{ bindHistoryError }}</p>
      <p v-else-if="dashboardLoading && !deviceHistoryMac" class="helper-copy">正在等待设备列表刷新，完成后可查看绑定历史。</p>
      <p v-else-if="lastDeletedDeviceMac && !deviceHistoryMac" class="helper-copy">最近删除设备 {{ lastDeletedDeviceMac }}，其当前绑定历史已不再视为有效状态。</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>时间</th><th>动作</th><th>原用户</th><th>新用户</th><th>原因</th></tr></thead>
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
              <td colspan="5">{{ deviceHistoryMac ? "当前设备还没有绑定历史。" : "请选择设备后查看绑定历史。" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>
