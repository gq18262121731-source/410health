<script setup lang="ts">
import type { HealthSample } from "../api/client";
import TrendChart from "../components/TrendChart.vue";

interface DebugRow {
  mac: string;
  deviceName: string;
  status: string;
  sample: HealthSample | null;
}

defineProps<{
  devicesCount: number;
  syncLabel: string;
  canGoCommunity: boolean;
  debugRows: DebugRow[];
  selectedDeviceMac: string;
  focusLatest: HealthSample | null;
  focusTrend: HealthSample[];
  trendWindowMinutes: number;
}>();

const emit = defineEmits<{
  reload: [];
  goCommunity: [];
  "update:selectedDeviceMac": [value: string];
  "update:trendWindowMinutes": [value: number];
}>();
</script>

<template>
  <section class="panel-grid relation-grid">
    <article class="panel relation-intro">
      <p class="kicker">Realtime Debug</p>
      <h2>设备趋势调试台</h2>
      <p class="lead">调试页只服务于设备联调和趋势核验，重点展示近时段趋势曲线与实时明细，不作为正式业务入口。</p>
      <div class="meta-block">
        <span class="meta-pill">设备数 {{ devicesCount }}</span>
        <span class="meta-pill">最近同步 {{ syncLabel }}</span>
        <button type="button" class="ghost-btn" @click="emit('reload')">立即刷新</button>
        <button v-if="canGoCommunity" type="button" class="ghost-btn" @click="emit('goCommunity')">返回业务页</button>
      </div>
    </article>

    <article class="panel relation-table">
      <h2>设备实时明细</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>设备</th>
              <th>状态</th>
              <th>包类型</th>
              <th>心率</th>
              <th>血氧</th>
              <th>体温</th>
              <th>电量</th>
              <th>步数</th>
              <th>环境温度</th>
              <th>表面温度</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in debugRows"
              :key="row.mac"
              :class="{ current: row.mac === selectedDeviceMac }"
              @click="emit('update:selectedDeviceMac', row.mac)"
            >
              <td><strong>{{ row.deviceName }}</strong><small>{{ row.mac }}</small></td>
              <td>{{ row.status }}</td>
              <td>{{ row.sample?.packet_type ?? "-" }}</td>
              <td>{{ row.sample?.heart_rate ?? "-" }}</td>
              <td>{{ row.sample?.blood_oxygen ?? "-" }}</td>
              <td>{{ row.sample?.temperature ?? "-" }}</td>
              <td>{{ row.sample?.battery ?? "-" }}</td>
              <td>{{ row.sample?.steps ?? "-" }}</td>
              <td>{{ row.sample?.ambient_temperature ?? "-" }}</td>
              <td>{{ row.sample?.surface_temperature ?? "-" }}</td>
              <td>{{ row.sample ? new Date(row.sample.timestamp).toLocaleString("zh-CN", { hour12: false }) : "-" }}</td>
            </tr>
            <tr v-if="!debugRows.length">
              <td colspan="11">暂无设备实时数据，请检查后端服务或设备接入状态。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article v-if="focusLatest" class="panel relation-table">
      <h2>选中设备详情</h2>
      <div class="table-wrap">
        <table>
          <tbody>
            <tr><th>设备 MAC</th><td>{{ focusLatest.device_mac }}</td></tr>
            <tr><th>UUID</th><td>{{ focusLatest.device_uuid ?? "-" }}</td></tr>
            <tr><th>包类型</th><td>{{ focusLatest.packet_type ?? "-" }}</td></tr>
            <tr><th>SOS</th><td>{{ focusLatest.sos_flag ? "是" : "否" }}</td></tr>
            <tr><th>血压</th><td>{{ focusLatest.blood_pressure ?? "-" }}</td></tr>
            <tr><th>步数</th><td>{{ focusLatest.steps ?? "-" }}</td></tr>
            <tr><th>上报时间</th><td>{{ new Date(focusLatest.timestamp).toLocaleString("zh-CN", { hour12: false }) }}</td></tr>
          </tbody>
        </table>
      </div>
    </article>

    <TrendChart
      v-if="selectedDeviceMac && focusTrend.length"
      :device-mac="selectedDeviceMac"
      :samples="focusTrend"
      :window-minutes="trendWindowMinutes"
      @change-window="emit('update:trendWindowMinutes', $event)"
    />
  </section>
</template>
