export interface DeviceRecord {
  id?: string;
  mac_address: string;
  device_name: string;
  user_id?: string | null;
  status: string;
  bind_status?: "unbound" | "bound" | "disabled";
  created_at?: string;
}

export interface DeviceBindLogRecord {
  id: string;
  device_id: string;
  old_user_id?: string | null;
  new_user_id?: string | null;
  action_type: string;
  operator_id?: string | null;
  reason?: string | null;
  created_at: string;
}

export interface HealthSample {
  device_mac: string;
  timestamp: string;
  heart_rate: number;
  temperature: number;
  blood_oxygen: number;
  ambient_temperature?: number | null;
  surface_temperature?: number | null;
  blood_pressure?: string;
  battery?: number;
  steps?: number | null;
  device_uuid?: string | null;
  packet_type?: string | null;
  sos_flag?: boolean;
  health_score?: number | null;
}

export interface AlarmRecord {
  id: string;
  device_mac: string;
  alarm_type: string;
  alarm_level: number;
  alarm_layer: string;
  message: string;
  acknowledged: boolean;
  created_at: string;
  anomaly_probability?: number | null;
}

export interface AlarmQueueItem {
  score: number;
  alarm: AlarmRecord;
}

export interface MobilePushRecord {
  id: string;
  alarm_id: string;
  device_mac: string;
  title: string;
  body: string;
  priority: number;
  created_at: string;
  delivered: boolean;
}

export interface AgentResponse {
  answer: string;
  references: string[];
  analysis?: Record<string, unknown>;
}

export interface AgentReportPeriod {
  start_at: string;
  end_at: string;
  duration_minutes: number;
  sample_count: number;
}

export interface AgentMetricReportItem {
  latest?: number | null;
  average?: number | null;
  min?: number | null;
  max?: number | null;
  trend?: string | null;
}

export interface AgentDeviceHealthReport {
  report_type: "device_health_report";
  device_mac: string;
  subject_name?: string | null;
  device_name?: string | null;
  generated_at: string;
  period: AgentReportPeriod;
  summary: string;
  risk_level: string;
  risk_flags: string[];
  key_findings: string[];
  recommendations: string[];
  metrics: Record<string, AgentMetricReportItem>;
  references: string[];
}

export interface CommunityOverview {
  clusters: Record<string, string[]>;
  device_count: number;
  intelligent_anomaly_score: number;
  trend?: Record<string, number>;
  risk_heatmap?: Array<Record<string, unknown>>;
}

export interface IntelligentDeviceAnalysis {
  device_mac: string;
  ready: boolean;
  probability?: number;
  score?: number;
  drift_score?: number;
  reconstruction_score?: number;
  reason?: string;
  message?: string;
}

export interface CommunityProfile {
  id: string;
  name: string;
  address: string;
  manager: string;
  hotline: string;
}

export interface ElderProfile {
  id: string;
  name: string;
  age: number;
  apartment: string;
  community_id: string;
  device_mac: string;
  device_macs?: string[];
  family_ids: string[];
}

export interface FamilyProfile {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  community_id: string;
  elder_ids: string[];
  login_username: string;
}

export interface CareDirectory {
  community: CommunityProfile;
  elders: ElderProfile[];
  families: FamilyProfile[];
}

export interface SessionUser {
  id: string;
  username: string;
  name: string;
  role: "family" | "community" | "admin" | "elder";
  community_id: string;
  family_id?: string | null;
}

export interface AuthAccountPreview {
  username: string;
  display_name: string;
  role: "family" | "community" | "admin" | "elder";
  family_id?: string | null;
  community_id: string;
  default_password: string;
}

export interface LoginResponse {
  token: string;
  user: SessionUser;
  expires_at: string;
}

export interface ElderRegisterRequest {
  name: string;
  phone: string;
  password: string;
  age: number;
  apartment: string;
  community_id?: string;
}

export interface FamilyRegisterRequest {
  name: string;
  phone: string;
  password: string;
  relationship: string;
  community_id?: string;
  login_username?: string | null;
}

export interface CommunityRegisterRequest {
  name: string;
  phone: string;
  password: string;
  community_id?: string;
  login_username?: string | null;
}

export interface UserRegisterResponse {
  id: string;
  name: string;
  role: "family" | "community" | "admin" | "elder";
  phone: string;
  created_at: string;
}

export interface CareFeatureAccess {
  basic_advice: boolean;
  device_metrics: boolean;
  health_evaluation: boolean;
  health_report: boolean;
}

export interface CareAccessDeviceMetric {
  device_mac: string;
  device_name: string;
  device_status: string;
  bind_status: string;
  elder_id?: string | null;
  elder_name?: string | null;
  latest_sample?: HealthSample | null;
}

export interface CareHealthReportSummary {
  device_mac: string;
  risk_level: string;
  sample_count: number;
  latest_health_score?: number | null;
  recommendations: string[];
  notable_events: string[];
}

export interface CareHealthEvaluationSummary {
  device_mac: string;
  risk_level: string;
  risk_flags: string[];
  latest_health_score?: number | null;
}

export interface CareAccessProfile {
  user_id: string;
  role: "family" | "community" | "admin" | "elder";
  community_id: string;
  family_id?: string | null;
  binding_state: "bound" | "unbound" | "not_applicable";
  bound_device_macs: string[];
  related_elder_ids: string[];
  capabilities: CareFeatureAccess;
  basic_advice: string;
  device_metrics: CareAccessDeviceMetric[];
  health_evaluations: CareHealthEvaluationSummary[];
  health_reports: CareHealthReportSummary[];
}

export interface FamilyRelationCreateRequest {
  elder_user_id: string;
  family_user_id: string;
  relation_type: string;
  is_primary?: boolean;
}

export interface FamilyRelationRecord {
  id: string;
  elder_user_id: string;
  family_user_id: string;
  relation_type: string;
  is_primary: boolean;
  status: string;
  created_at: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
const WS_BASE = (import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `Request failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail || `Request failed: ${status}`;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as {
        detail?:
          | string
          | { message?: string; code?: string }
          | Array<{ msg?: string; loc?: Array<string | number> }>;
      };
      const detailPayload = payload.detail;
      if (typeof detailPayload === "string") {
        detail = detailPayload;
      } else if (Array.isArray(detailPayload) && detailPayload.length) {
        const first = detailPayload[0];
        const message = String(first.msg ?? "");
        if (message.includes("INVALID_MAC_ADDRESS")) detail = "设备 MAC 格式错误，请使用 AA:BB:CC:DD:EE:FF。";
        else if (message.includes("INVALID_MAC_PREFIX")) detail = "设备 MAC 前缀不在允许范围内。";
        else if (message.includes("question")) detail = "请输入更具体的问题后再试。";
        else if (message.includes("mode")) detail = "请求模式无效，请联系开发人员检查前端参数。";
        else if (message.includes("role")) detail = "请求角色无效，请联系开发人员检查前端参数。";
        else detail = message.replace(/^Value error,\s*/i, "") || detail;
      } else if (detailPayload && !Array.isArray(detailPayload) && detailPayload.message) {
        detail = detailPayload.message;
      } else if (detailPayload && !Array.isArray(detailPayload) && detailPayload.code) {
        detail = detailPayload.code;
      }
    } catch {
      // ignore non-json error bodies
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

function withBearer(token?: string): HeadersInit | undefined {
  if (!token) return undefined;
  return { Authorization: `Bearer ${token}` };
}

function jsonHeaders(token?: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    ...(withBearer(token) ?? {}),
  };
}

export const api = {
  listDevices: () => requestJson<DeviceRecord[]>(`${API_BASE}/devices`),
  getDevice: (mac: string) => requestJson<DeviceRecord>(`${API_BASE}/devices/${mac}`),
  registerDevice: (payload: { mac_address: string; device_name?: string; user_id?: string | null }, token?: string) =>
    requestJson<DeviceRecord>(`${API_BASE}/devices/register`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  bindDevice: (payload: { mac_address: string; target_user_id: string; operator_id?: string | null }, token?: string) =>
    requestJson<DeviceBindLogRecord>(`${API_BASE}/devices/bind`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  unbindDevice: (payload: { mac_address: string; operator_id?: string | null; reason?: string | null }, token?: string) =>
    requestJson<DeviceBindLogRecord>(`${API_BASE}/devices/unbind`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  rebindDevice: (payload: {
    mac_address: string;
    new_user_id: string;
    operator_id?: string | null;
    reason?: string | null;
  }, token?: string) =>
    requestJson<DeviceBindLogRecord>(`${API_BASE}/devices/rebind`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  deleteDevice: (mac: string, token?: string) =>
    requestJson<DeviceRecord>(`${API_BASE}/devices/${mac}`, {
      method: "DELETE",
      headers: withBearer(token),
    }),
  listDeviceBindLogs: (mac: string) =>
    requestJson<DeviceBindLogRecord[]>(`${API_BASE}/devices/${mac}/bind-logs`),
  registerElder: (payload: ElderRegisterRequest, token?: string) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/users/elders/register`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  registerFamily: (payload: FamilyRegisterRequest, token?: string) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/users/families/register`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  bindFamilyRelation: (payload: FamilyRelationCreateRequest, token?: string) =>
    requestJson<FamilyRelationRecord>(`${API_BASE}/relations/family-bind`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  getRealtime: (mac: string) => requestJson<HealthSample>(`${API_BASE}/health/realtime/${mac}`),
  getTrend: (mac: string, minutes = 180, limit = 120) =>
    requestJson<HealthSample[]>(`${API_BASE}/health/trend/${mac}?minutes=${minutes}&limit=${limit}`),
  getCommunityOverview: () =>
    requestJson<CommunityOverview>(`${API_BASE}/health/community/overview`),
  getIntelligentAnalysis: (mac: string) =>
    requestJson<IntelligentDeviceAnalysis>(`${API_BASE}/health/intelligent/${mac}`),
  listAlarms: () => requestJson<AlarmRecord[]>(`${API_BASE}/alarms?active_only=true`),
  listAlarmQueue: () => requestJson<AlarmQueueItem[]>(`${API_BASE}/alarms/queue`),
  listMobilePushes: (limit = 10) =>
    requestJson<MobilePushRecord[]>(`${API_BASE}/alarms/mobile-pushes?limit=${limit}`),
  ackAlarm: (alarmId: string) =>
    requestJson<AlarmRecord>(`${API_BASE}/alarms/${alarmId}/acknowledge`, { method: "POST" }),
  analyze: (payload: {
    device_mac: string;
    question: string;
    role: string;
    mode: string;
    history_limit?: number;
    history_minutes?: number;
  }) =>
    requestJson<AgentResponse>(`${API_BASE}/chat/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  analyzeCommunity: (payload: {
    question: string;
    role: string;
    mode: string;
    history_minutes?: number;
    per_device_limit?: number;
    device_macs?: string[];
  }) =>
    requestJson<AgentResponse>(`${API_BASE}/chat/analyze/community`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  generateDeviceHealthReport: (payload: {
    device_mac: string;
    start_at: string;
    end_at: string;
    role?: string;
    mode?: string;
  }) =>
    requestJson<AgentDeviceHealthReport>(`${API_BASE}/chat/report/device`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getCareDirectory: () => requestJson<CareDirectory>(`${API_BASE}/care/directory`),
  getFamilyCareDirectory: (familyId: string) =>
    requestJson<CareDirectory>(`${API_BASE}/care/directory/family/${familyId}`),
  listMockAccounts: () => requestJson<AuthAccountPreview[]>(`${API_BASE}/auth/mock-accounts`),
  login: (payload: { username: string; password: string }) =>
    requestJson<LoginResponse>(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  loginMock: (payload: { username: string; password: string }) =>
    requestJson<LoginResponse>(`${API_BASE}/auth/mock-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  publicRegisterElder: (payload: ElderRegisterRequest) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/auth/register/elder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  publicRegisterFamily: (payload: FamilyRegisterRequest) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/auth/register/family`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  publicRegisterCommunityStaff: (payload: CommunityRegisterRequest) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/auth/register/community-staff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  registerCommunityStaff: (payload: CommunityRegisterRequest, token?: string) =>
    requestJson<UserRegisterResponse>(`${API_BASE}/users/community-staff/register`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
    }),
  me: (token: string) =>
    requestJson<SessionUser>(`${API_BASE}/auth/me`, {
      headers: withBearer(token),
    }),
  getCareAccessProfile: (token: string) =>
    requestJson<CareAccessProfile>(`${API_BASE}/care/access-profile/me`, {
      headers: withBearer(token),
    }),
  healthSocket: (mac: string) => new WebSocket(`${WS_BASE}/ws/health/${mac}`),
  alarmSocket: () => new WebSocket(`${WS_BASE}/ws/alarms`),
};
