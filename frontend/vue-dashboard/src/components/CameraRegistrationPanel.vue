<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Camera, Laptop, Plus, RefreshCw, Router, ShieldCheck } from "lucide-vue-next";
import { api, type CameraSourceRegistrationResponse } from "../api/client";

const emit = defineEmits<{
  sourceChange: [];
}>();

const registry = ref<CameraSourceRegistrationResponse | null>(null);
const deviceId = ref("");
const displayName = ref("");
const busy = ref(false);
const message = ref("");
const errorMessage = ref("");

const activeSource = computed(() => registry.value?.active_source ?? null);
const externalSources = computed(() =>
  (registry.value?.sources ?? []).filter((source) => source.source_mode !== "local"),
);

const activeLabel = computed(() => {
  if (!activeSource.value) return "未选择";
  if (activeSource.value.source_mode === "local") return "本地摄像头";
  return activeSource.value.name || activeSource.value.device_id || "外接摄像头";
});

async function refreshRegistry() {
  try {
    registry.value = await api.getCameraSourceRegistration();
    errorMessage.value = "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "摄像头注册状态读取失败";
  }
}

async function selectLocal() {
  busy.value = true;
  try {
    registry.value = await api.selectLocalCameraSource();
    message.value = "已切换到本地摄像头。";
    errorMessage.value = "";
    emit("sourceChange");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "本地摄像头切换失败";
  } finally {
    busy.value = false;
  }
}

async function registerExternal() {
  const id = deviceId.value.trim();
  if (!id) {
    errorMessage.value = "请先填写外接摄像头设备 ID。";
    return;
  }

  busy.value = true;
  try {
    registry.value = await api.registerExternalCameraSource({
      device_id: id,
      name: displayName.value.trim() || undefined,
    });
    message.value = "外接摄像头已注册并选中。";
    errorMessage.value = "";
    deviceId.value = "";
    displayName.value = "";
    emit("sourceChange");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "外接摄像头注册失败";
  } finally {
    busy.value = false;
  }
}

async function selectSource(cameraId: string) {
  busy.value = true;
  try {
    registry.value = await api.selectCameraSource(cameraId);
    message.value = "摄像头来源已切换。";
    errorMessage.value = "";
    emit("sourceChange");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "摄像头切换失败";
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  void refreshRegistry();
});
</script>

<template>
  <section class="camera-registration-panel">
    <div class="camera-registration-panel__intro">
      <div class="camera-registration-panel__icon">
        <Camera :size="22" />
      </div>
      <div>
        <p class="section-eyebrow">CAMERA ACCESS</p>
        <h3>摄像头接入</h3>
        <p>本地摄像头可直接启用；外接摄像头填写设备 ID 后注册，视频流仍由后端统一转发。</p>
      </div>
      <button type="button" class="camera-registration-panel__refresh" :disabled="busy" @click="refreshRegistry">
        <RefreshCw :size="15" />
        刷新
      </button>
    </div>

    <div class="camera-registration-panel__grid">
      <button
        type="button"
        class="camera-source-tile"
        :class="{ 'is-active': activeSource?.camera_id === 'local' }"
        :disabled="busy"
        @click="selectLocal"
      >
        <Laptop :size="20" />
        <span>本地摄像头</span>
        <small>无需注册，直接调用电脑摄像头。</small>
      </button>

      <form class="camera-registration-panel__form" @submit.prevent="registerExternal">
        <div>
          <label for="external-camera-id">外接摄像头设备 ID</label>
          <input id="external-camera-id" v-model="deviceId" type="text" placeholder="例如 VSTA705342RHKCT" />
        </div>
        <div>
          <label for="external-camera-name">显示名称</label>
          <input id="external-camera-name" v-model="displayName" type="text" placeholder="例如 客厅摄像头" />
        </div>
        <button type="submit" :disabled="busy">
          <Plus :size="16" />
          注册外接摄像头
        </button>
      </form>
    </div>

    <div class="camera-registration-panel__footer">
      <span class="camera-registration-panel__active">
        <ShieldCheck :size="15" />
        当前：{{ activeLabel }}
      </span>
      <button
        v-for="source in externalSources"
        :key="source.camera_id"
        type="button"
        class="camera-registration-panel__chip"
        :class="{ 'is-active': source.camera_id === activeSource?.camera_id }"
        :disabled="busy"
        @click="selectSource(source.camera_id)"
      >
        <Router :size="14" />
        {{ source.name || source.device_id || source.camera_id }}
      </button>
    </div>

    <p v-if="message" class="camera-registration-panel__message">{{ message }}</p>
    <p v-if="errorMessage" class="camera-registration-panel__error">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.camera-registration-panel {
  border: 1px solid rgba(20, 148, 135, 0.22);
  border-radius: 24px;
  padding: clamp(18px, 3vw, 26px);
  background:
    radial-gradient(circle at 8% 0%, rgba(43, 201, 178, 0.18), transparent 34%),
    linear-gradient(135deg, rgba(248, 253, 250, 0.98), rgba(239, 248, 255, 0.94));
  box-shadow: 0 18px 46px rgba(25, 83, 93, 0.08);
}

.camera-registration-panel__intro,
.camera-registration-panel__grid,
.camera-registration-panel__footer {
  display: flex;
  gap: 14px;
}

.camera-registration-panel__intro {
  align-items: flex-start;
}

.camera-registration-panel__icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 18px;
  color: #08786e;
  background: rgba(18, 158, 144, 0.12);
}

.camera-registration-panel h3 {
  margin: 2px 0 4px;
  color: #102d35;
  font-size: clamp(20px, 2.4vw, 28px);
}

.camera-registration-panel p {
  margin: 0;
  color: #527078;
}

.camera-registration-panel__refresh,
.camera-registration-panel__form button,
.camera-registration-panel__chip,
.camera-source-tile {
  border: 0;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.camera-registration-panel__refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  border-radius: 999px;
  padding: 9px 13px;
  color: #0b776e;
  background: rgba(255, 255, 255, 0.76);
}

.camera-registration-panel__grid {
  align-items: stretch;
  margin-top: 18px;
}

.camera-source-tile {
  min-width: 220px;
  display: grid;
  gap: 8px;
  align-content: center;
  justify-items: start;
  border-radius: 20px;
  padding: 18px;
  color: #17424b;
  background: rgba(255, 255, 255, 0.78);
  text-align: left;
}

.camera-source-tile.is-active,
.camera-registration-panel__chip.is-active {
  color: #064a45;
  background: rgba(75, 219, 193, 0.26);
  box-shadow: inset 0 0 0 1px rgba(11, 132, 120, 0.28);
}

.camera-source-tile span {
  font-weight: 800;
}

.camera-source-tile small {
  color: #63828a;
}

.camera-registration-panel__form {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 0.75fr) auto;
  gap: 12px;
  align-items: end;
  border-radius: 20px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.7);
}

.camera-registration-panel__form label {
  display: block;
  margin-bottom: 7px;
  color: #46636b;
  font-size: 12px;
  font-weight: 800;
}

.camera-registration-panel__form input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(25, 120, 114, 0.18);
  border-radius: 14px;
  padding: 12px 13px;
  color: #163940;
  background: rgba(255, 255, 255, 0.86);
  outline: none;
}

.camera-registration-panel__form input:focus {
  border-color: rgba(14, 133, 122, 0.55);
  box-shadow: 0 0 0 4px rgba(14, 133, 122, 0.1);
}

.camera-registration-panel__form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: 15px;
  padding: 12px 16px;
  color: white;
  background: #0f8c80;
  font-weight: 800;
}

.camera-registration-panel__footer {
  flex-wrap: wrap;
  align-items: center;
  margin-top: 14px;
}

.camera-registration-panel__active,
.camera-registration-panel__chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 999px;
  padding: 9px 12px;
  color: #315a63;
  background: rgba(255, 255, 255, 0.72);
  font-size: 13px;
  font-weight: 800;
}

.camera-registration-panel__message,
.camera-registration-panel__error {
  margin-top: 12px;
  font-weight: 700;
}

.camera-registration-panel__message {
  color: #08786e;
}

.camera-registration-panel__error {
  color: #b42318;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

button:not(:disabled):hover {
  transform: translateY(-1px);
}

@media (max-width: 820px) {
  .camera-registration-panel__intro,
  .camera-registration-panel__grid,
  .camera-registration-panel__form {
    display: grid;
  }

  .camera-registration-panel__refresh {
    margin-left: 0;
    justify-self: start;
  }

  .camera-registration-panel__form {
    grid-template-columns: 1fr;
  }
}
</style>
