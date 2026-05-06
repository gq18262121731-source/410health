# VERSION_HISTORY.md

## v1.0 (2026-04-29)
- 文件路径：`backend/services/health_stability_service.py`
- 修改说明：修复健康评分在 `spo2` 等生命体征越界时直接报错的问题，改为优先复用最近一次合法值并进行边界纠偏。
- 修改前的代码片段：
```python
    def _process_state(
        self,
        *,
        state: DeviceStabilityState,
        timestamp: datetime,
        vitals: Mapping[str, Any],
    ) -> StabilitySnapshot:
        normalized_timestamp = self._normalize_timestamp(timestamp)
        raw_vitals = self._normalize_vitals(vitals)
        state.history.append(BufferedPoint(timestamp=normalized_timestamp, vitals=raw_vitals))
```

## v1.14 (2026-04-29)
- 文件路径：`backend/services/care_service.py`
- 修改说明：将 demo 登录账号构建改为纯种子数据，不再依赖设备目录聚合，避免 `community_admin` 登录被设备/目录加载阻塞。
- 修改前的代码片段：
```python
    def _build_demo_accounts(self) -> list[AccountRecord]:
        directory = self.get_demo_directory()
        community_user = SessionUser(
            id=directory.community.id,
            username="community_admin",
            ...
        )
        ...
        for family in directory.families:
            ...
            for elder_id in family.elder_ids:
                elder = next((item for item in directory.elders if item.id == elder_id), None)
```
- 修改后的代码片段：
```python
    def _build_demo_accounts(self) -> list[AccountRecord]:
        community = self._community_profile()
        records = [
            AccountRecord(
                username="community_admin",
                password=self._settings.seed_default_password,
                user=SessionUser(
                    id=community.id,
                    username="community_admin",
                    name="社区管理员",
                    role=UserRole.COMMUNITY,
                    community_id=community.id,
                    family_id=None,
                ),
            )
        ]

        elders_by_family: dict[str, list[DemoElderSeed]] = {}
        for elder_seed in DEMO_ELDER_SEEDS:
            elders_by_family.setdefault(elder_seed.family_id, []).append(elder_seed)
        ...
```

## v1.13 (2026-04-29)
- 文件路径：`backend/services/health_score_service.py`
- 修改说明：当静态健康评分模型工件缺失时，结构化评分自动降级为规则评分，避免每条样本持续抛出 `ModelArtifactMissingError`。
- 修改前的代码片段：
```python
            response = self._score_snapshot(
                snapshot=snapshot,
                elderly_id=elderly_id,
                device_id=device_id,
                evaluated_at=evaluated_at,
                stateful_stability=stateful_stability,
            )
```

```python
        except ModelArtifactMissingError as exc:
            raise ServiceError(
                code="MODEL_ARTIFACT_MISSING",
                message=str(exc),
                status_code=503,
            ) from exc
```
- 修改后的代码片段：
```python
            response = self._score_snapshot_with_fallback(
                snapshot=snapshot,
                elderly_id=elderly_id,
                device_id=device_id,
                evaluated_at=evaluated_at,
                stateful_stability=stateful_stability,
            )
```

```python
    def _score_snapshot_with_fallback(
        self,
        *,
        snapshot: StabilitySnapshot,
        elderly_id: str,
        device_id: str,
        evaluated_at: datetime,
        stateful_stability: bool,
    ) -> HealthScoreResponse:
        try:
            return self._score_snapshot(
                snapshot=snapshot,
                elderly_id=elderly_id,
                device_id=device_id,
                evaluated_at=evaluated_at,
                stateful_stability=stateful_stability,
            )
        except ModelArtifactMissingError as exc:
            LOGGER.warning(
                "Static health model artifacts missing; using rule-only fallback for device=%s elderly=%s: %s",
                device_id,
                elderly_id,
                exc,
            )
            return self._build_rule_only_response(
                snapshot=snapshot,
                elderly_id=elderly_id,
                device_id=device_id,
                evaluated_at=evaluated_at,
                stateful_stability=stateful_stability,
                score_adjustment_reason="Model artifacts missing; rule-only fallback applied.",
            )
```

## v1.12 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/composables/useSessionAuth.ts`
- 修改说明：按要求回退登录与会话恢复改动，恢复为原始登录逻辑，不再增加超时和恢复状态控制。
- 修改前的代码片段：
```ts
const AUTH_REQUEST_TIMEOUT_MS = 8000;

async function withTimeout<T>(task: Promise<T>, timeoutMs = AUTH_REQUEST_TIMEOUT_MS): Promise<T> {
  let timer: number | null = null;
  try {
    return await Promise.race([
      task,
      new Promise<T>((_, reject) => {
        timer = window.setTimeout(() => {
          reject(new Error("请求超时，请确认后端服务是否正常。"));
        }, timeoutMs);
      }),
    ]);
  } finally {
    if (timer !== null) {
      window.clearTimeout(timer);
    }
  }
}
```

```ts
  const restoreLoading = ref(false);
  const restoreAttempted = ref(false);
```
- 修改后的代码片段：
```ts
export const SESSION_KEY = "ai_health_demo_session_token";

export function getStoredSessionToken() {
  return localStorage.getItem(SESSION_KEY) ?? "";
}
```

```ts
  const authLoading = ref(false);
  const authError = ref("");
```

- 文件路径：`frontend/vue-dashboard/src/App.vue`
- 修改说明：移除登录态恢复中的过渡页，恢复原始登录页切换逻辑。
- 修改前的代码片段：
```vue
  <div v-if="restoreLoading && !restoreAttempted" class="app-boot-screen">
    <div class="app-boot-screen__panel">
      <div class="app-boot-screen__spinner" aria-hidden="true"></div>
      <strong>正在恢复登录状态</strong>
      <p>请稍候，我们正在确认当前会话。</p>
    </div>
  </div>

  <LoginPage
    v-else-if="!isLoggedIn"
```
- 修改后的代码片段：
```vue
  <LoginPage
    v-if="!isLoggedIn"
```

## v1.11 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/composables/useSessionAuth.ts`
- 修改说明：为登录和会话恢复请求增加 8 秒超时保护，避免前端无限停留在“登录中”或“恢复登录状态”。
- 修改前的代码片段：
```ts
      const result = await api.login({
        username: loginUsername.value.trim(),
        password: loginPassword.value,
      });
```

```ts
      const user = await api.me(token);
      sessionUser.value = user;
```
- 修改后的代码片段：
```ts
      const result = await withTimeout(
        api.login({
          username: loginUsername.value.trim(),
          password: loginPassword.value,
        }),
      );
```

```ts
      const user = await withTimeout(api.me(token));
      sessionUser.value = user;
```

## v1.10 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/views/CommunityAgentPage.vue`
- 修改说明：将智能体工作台底部的四个快捷功能按钮移动到空状态引导区中部，避免与输入区重复。
- 修改前的代码片段：
```vue
          <div v-if="!workbench.messages.value.length" class="agent-empty-state">
            <div class="agent-empty-state__icon">
              <Sparkles :size="20" />
            </div>
            <h2>从一个明确能力开始，让智能体直接进入分析</h2>
            <p>上方下拉栏用于固定分析对象、时间范围、智能体能力和模型来源，避免来回切换按钮。</p>
          </div>
```

```vue
      <footer class="agent-composer">
        <div class="agent-composer__quick">
          <button
            v-for="action in quickSuggestions"
            :key="action.workflow"
            type="button"
            class="agent-quick-pill"
            @click="submitSuggestedWorkflow(action.workflow, action.prompt)"
          >
            <Sparkles :size="14" />
            {{ action.label }}
          </button>
        </div>
```
- 修改后的代码片段：
```vue
          <div v-if="!workbench.messages.value.length" class="agent-empty-state">
            <div class="agent-empty-state__icon">
              <Sparkles :size="20" />
            </div>
            <h2>从一个明确能力开始，让智能体直接进入分析</h2>
            <p>上方下拉栏用于固定分析对象、时间范围、智能体能力和模型来源，避免来回切换按钮。</p>
            <div class="agent-empty-state__actions">
              <button
                v-for="action in quickSuggestions"
                :key="action.workflow"
                type="button"
                class="agent-quick-pill"
                @click="submitSuggestedWorkflow(action.workflow, action.prompt)"
              >
                <Sparkles :size="14" />
                {{ action.label }}
              </button>
            </div>
          </div>
```

```vue
      <footer class="agent-composer">
        <label class="agent-composer__field">
```

## v1.9 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/composables/useSessionAuth.ts`
- 修改说明：刷新页面时增加会话恢复状态，并且只有在明确未授权时才清除本地 token，避免刷新后误回到登录页。
- 修改前的代码片段：
```ts
  const authLoading = ref(false);
  const authError = ref("");
```

```ts
  async function restoreSession() {
    const token = getStoredSessionToken();
    if (!token) return;

    const user = await api.me(token).catch(() => null);
    if (!user) {
      localStorage.removeItem(SESSION_KEY);
      return;
    }

    sessionUser.value = user;
  }
```
- 修改后的代码片段：
```ts
  const authLoading = ref(false);
  const authError = ref("");
  const restoreLoading = ref(false);
  const restoreAttempted = ref(false);
```

```ts
  async function restoreSession() {
    const token = getStoredSessionToken();
    restoreLoading.value = true;
    authError.value = "";

    if (!token) {
      restoreAttempted.value = true;
      restoreLoading.value = false;
      return;
    }

    try {
      const user = await api.me(token);
      sessionUser.value = user;
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        localStorage.removeItem(SESSION_KEY);
        return;
      }
      authError.value = "会话恢复失败，请检查后端连接后重试。";
    } finally {
      restoreAttempted.value = true;
      restoreLoading.value = false;
    }
  }
```

- 文件路径：`frontend/vue-dashboard/src/App.vue`
- 修改说明：应用启动时在会话恢复完成前显示恢复中的过渡页，避免先闪回登录页。
- 修改前的代码片段：
```vue
<template>
  <LoginPage
    v-if="!isLoggedIn"
```
- 修改后的代码片段：
```vue
<template>
  <div v-if="restoreLoading && !restoreAttempted" class="app-boot-screen">
    <div class="app-boot-screen__panel">
      <div class="app-boot-screen__spinner" aria-hidden="true"></div>
      <strong>正在恢复登录状态</strong>
      <p>请稍候，我们正在确认当前会话。</p>
    </div>
  </div>

  <LoginPage
    v-else-if="!isLoggedIn"
```

## v1.8 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/components/layout/AppShell.vue`
- 修改说明：为单头卡页面补回右上角管理员身份信息和退出按钮，避免隐藏重复头卡后丢失账户操作入口。
- 修改前的代码片段：
```vue
const showGlobalHeader = computed(
  () => !isCommunityWorkspace.value || !mergedHeaderPages.has(props.activePage),
);
```

```vue
      <div class="app-shell__content">
        <slot />
      </div>
```
- 修改后的代码片段：
```vue
const showGlobalHeader = computed(
  () => !isCommunityWorkspace.value || !mergedHeaderPages.has(props.activePage),
);
const showMergedPageAccountBar = computed(
  () => isCommunityWorkspace.value && mergedHeaderPages.has(props.activePage),
);
const roleLabel = computed(() => {
  switch (props.sessionUser.role) {
    case "community":
      return "社区值守";
    case "family":
      return "家属查看";
    case "admin":
      return "系统管理";
    default:
      return "成员账号";
  }
});
```

```vue
      <div class="app-shell__content">
        <div v-if="showMergedPageAccountBar" class="app-shell__account-bar">
          <div class="app-shell__user-info">
            <span class="app-shell__user-name">{{ sessionUser.name }}</span>
            <span class="app-shell__user-role">
              <ShieldCheck :size="14" />
              {{ roleLabel }}
            </span>
          </div>

          <button type="button" class="app-shell__logout-btn" @click="emit('logout')">
            <LogOut :size="16" />
            <span>退出</span>
          </button>
        </div>

        <slot />
      </div>
```

## v1.7 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/components/layout/AppShell.vue`
- 修改说明：将设备拓扑、成员设备和智能体工作台页也纳入单头卡模式，统一隐藏重复的顶部全局头部卡片。
- 修改前的代码片段：
```vue
const showGlobalHeader = computed(
  () => !isCommunityWorkspace.value || props.activePage !== "overview",
);
```
- 修改后的代码片段：
```vue
const mergedHeaderPages = new Set<PageKey>(["overview", "topology", "members", "agent"]);
const showGlobalHeader = computed(
  () => !isCommunityWorkspace.value || !mergedHeaderPages.has(props.activePage),
);
```

## v1.6 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/components/layout/AppShell.vue`
- 修改说明：总览监护页隐藏重复的全局头部卡片，只保留页面内那张完整监护头卡。
- 修改前的代码片段：
```vue
const isCommunityWorkspace = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);
```

```vue
      <GlobalHeader
        :session-user="sessionUser"
        :active-alarm-count="activeAlarmCount"
        :active-page="activePage"
        @logout="emit('logout')"
      />
```
- 修改后的代码片段：
```vue
const isCommunityWorkspace = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);
const showGlobalHeader = computed(
  () => !isCommunityWorkspace.value || props.activePage !== "overview",
);
```

```vue
      <GlobalHeader
        v-if="showGlobalHeader"
        :session-user="sessionUser"
        :active-alarm-count="activeAlarmCount"
        :active-page="activePage"
        @logout="emit('logout')"
      />
```

```python
    def _normalize_vitals(self, vitals: Mapping[str, Any]) -> dict[str, Any]:
        validated = validate_inference_record(vitals)
        return {
            "heart_rate": float(validated["heart_rate"]),
            "spo2": float(validated["spo2"]),
            "sbp": float(validated["sbp"]),
            "dbp": float(validated["dbp"]),
            "body_temp": float(validated["body_temp"]),
            "fall_detection": bool(validated.get("fall_detection", False)),
            "data_accuracy": float(validated.get("data_accuracy", 100.0)),
        }
```
- 修改后的代码片段：
```python
    def _process_state(
        self,
        *,
        state: DeviceStabilityState,
        timestamp: datetime,
        vitals: Mapping[str, Any],
    ) -> StabilitySnapshot:
        normalized_timestamp = self._normalize_timestamp(timestamp)
        fallback_vitals = state.history[-1].vitals if state.history else None
        raw_vitals = self._normalize_vitals(vitals, fallback_vitals=fallback_vitals)
        state.history.append(BufferedPoint(timestamp=normalized_timestamp, vitals=raw_vitals))
```

```python
    def _normalize_vitals(
        self,
        vitals: Mapping[str, Any],
        *,
        fallback_vitals: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            validated = validate_inference_record(vitals)
        except DataValidationError:
            validated = self._repair_inference_record(vitals, fallback_vitals=fallback_vitals)
        return {
            "heart_rate": float(validated["heart_rate"]),
            "spo2": float(validated["spo2"]),
            "sbp": float(validated["sbp"]),
            "dbp": float(validated["dbp"]),
            "body_temp": float(validated["body_temp"]),
            "fall_detection": bool(validated.get("fall_detection", False)),
            "data_accuracy": float(validated.get("data_accuracy", 100.0)),
        }

    def _repair_inference_record(
        self,
        vitals: Mapping[str, Any],
        *,
        fallback_vitals: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        repaired: dict[str, Any] = dict(vitals)
        repair_notes: list[str] = []

        for column, (minimum, maximum) in VALUE_RANGES.items():
            raw_value = vitals.get(column)
            fallback_value = fallback_vitals.get(column) if fallback_vitals else None
            normalized_value, repair_note = self._sanitize_numeric_value(
                column=column,
                raw_value=raw_value,
                fallback_value=fallback_value,
                minimum=minimum,
                maximum=maximum,
            )
            repaired[column] = normalized_value
            if repair_note:
                repair_notes.append(repair_note)

        repaired["fall_detection"] = bool(vitals.get("fall_detection", False))

        if repair_notes:
            LOGGER.warning(
                "Repaired invalid vitals before stability scoring: notes=%s raw=%s fallback=%s repaired=%s",
                "; ".join(repair_notes),
                dict(vitals),
                dict(fallback_vitals) if fallback_vitals else None,
                repaired,
            )

        return validate_inference_record(repaired)
```

## v1.1 (2026-04-29)
- 文件路径：`backend/services/health_stability_service.py`
- 修改说明：修复健康稳定性服务对旧版 Python 解释器不兼容的 `datetime.UTC` 导入问题。
- 修改前的代码片段：
```python
from datetime import UTC, datetime, timedelta
```

```python
    def _normalize_timestamp(self, value: Any, fallback_index: int | None = None) -> datetime:
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, str) and value.strip():
            timestamp = datetime.fromisoformat(value)
        else:
            base = datetime.now(UTC)
            offset = fallback_index or 0
            timestamp = base + timedelta(seconds=offset * self.default_sample_interval_seconds)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
```
- 修改后的代码片段：
```python
from datetime import datetime, timedelta, timezone
```

```python
    def _normalize_timestamp(self, value: Any, fallback_index: int | None = None) -> datetime:
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, str) and value.strip():
            timestamp = datetime.fromisoformat(value)
        else:
            base = datetime.now(timezone.utc)
            offset = fallback_index or 0
            timestamp = base + timedelta(seconds=offset * self.default_sample_interval_seconds)
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
```

## v1.2 (2026-04-29)
- 文件路径：`frontend/vue-dashboard/src/views/CommunityAgentPage.vue`
- 修改说明：将智能体工作台原本分离的内容区和输入区合并为一张整体卡片。
- 修改前的代码片段：
```vue
    <section class="agent-shell">
      <div class="agent-controls">
        ...
      </div>

      <div class="agent-chat-surface">
        ...
      </div>
    </section>

    <footer class="agent-composer">
      ...
    </footer>
```
- 修改后的代码片段：
```vue
    <section class="agent-shell agent-shell--unified">
      <div class="agent-controls">
        ...
      </div>

      <div class="agent-chat-surface">
        ...
      </div>

      <footer class="agent-composer">
        ...
      </footer>
    </section>
```

## v1.3 (2026-04-29)
- 文件路径：`docker/docker-compose.yml`
- 修改说明：移除过时的 `version` 字段，并取消 Redis 对宿主机 `6379` 端口的暴露以解决容器启动端口冲突。
- 修改前的代码片段：
```yaml
version: "3.9"

services:
  redis:
    image: redis:7
    container_name: ai-health-iot-redis
    ports:
      - "6379:6379"
```
- 修改后的代码片段：
```yaml
services:
  redis:
    image: redis:7
    container_name: ai-health-iot-redis
```

## v1.4 (2026-04-29)
- 文件路径：`backend/dependencies.py`
- 修改说明：在结构化健康评分持久化前跳过明显无效的中间态样本，避免 `hr=0/spo2=0/temp=0.0` 持续触发评分异常。
- 修改前的代码片段：
```python
def _persist_structured_health_score(sample: HealthSample, device: DeviceRecord) -> None:
    """Persist ML/rule split scores so dashboard can render rule/model breakdown."""
    systolic, diastolic = sample.blood_pressure_pair
    vitals = VitalSignsPayload(
```
- 修改后的代码片段：
```python
def _persist_structured_health_score(sample: HealthSample, device: DeviceRecord) -> None:
    """Persist ML/rule split scores so dashboard can render rule/model breakdown."""
    if (
        sample.heart_rate <= 0
        or sample.blood_oxygen <= 0
        or sample.temperature <= 0
    ):
        logger.info(
            "Skipping structured score persistence for %s due to invalid vitals: hr=%s spo2=%s temp=%s packet_type=%s",
            sample.device_mac,
            sample.heart_rate,
            sample.blood_oxygen,
            sample.temperature,
            sample.packet_type,
        )
        return

    systolic, diastolic = sample.blood_pressure_pair
    vitals = VitalSignsPayload(
```

## v1.5 (2026-04-29)
- 文件路径：`backend/services/health_stability_service.py`
- 修改说明：删除健康稳定性服务中遗留的 `datetime.now(UTC)` 语句，避免运行时 `NameError` 风险。
- 修改前的代码片段：
```python
        else:
            base = datetime.now(UTC)
            base = datetime.now(timezone.utc)
            offset = fallback_index or 0
```
- 修改后的代码片段：
```python
        else:
            base = datetime.now(timezone.utc)
            offset = fallback_index or 0
```

## v1.15 (2026-04-29)
- 文件路径：`backend/services/care_service.py`
- 修改说明：让演示账号如 `community_admin` 优先走 demo 登录，避免被正式账号认证拖慢并误进空社区。
- 修改前的代码片段：
```python
    def login(self, username: str, password: str) -> LoginResponse | None:
        formal = self.login_formal(username, password)
        if formal is not None:
            return formal
        return self.login_demo(username, password)
```
- 修改后的代码片段：
```python
    def login(self, username: str, password: str) -> LoginResponse | None:
        normalized_username = username.strip().lower()
        demo_usernames = {record.username for record in self._build_demo_accounts()}

        # Demo operators such as `community_admin` should enter the seeded demo
        # workspace immediately instead of blocking on formal-user lookups.
        if normalized_username in demo_usernames:
            demo = self.login_demo(username, password)
            if demo is not None:
                return demo

        formal = self.login_formal(username, password)
        if formal is not None:
            return formal
        return self.login_demo(username, password)
```
