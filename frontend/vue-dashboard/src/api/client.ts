export interface DeviceRecord {
  id?: string;
  mac_address: string;
  device_name: string;
  model_code?: string;
  ingest_mode?: "serial" | "mqtt" | "ble" | "mock";
  service_uuid?: string;
  device_uuid?: string;
  user_id?: string | null;
  status: string;
  activation_state?: "pending" | "active";
  bind_status?: "unbound" | "bound" | "disabled";
  last_seen_at?: string | null;
  last_packet_type?: string | null;
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
  source?: "serial" | "mock" | "mqtt" | "ble";
  ambient_temperature?: number | null;
  surface_temperature?: number | null;
  blood_pressure?: string;
  battery?: number;
  steps?: number | null;
  device_uuid?: string | null;
  packet_type?: string | null;
  sos_flag?: boolean;
  sos_value?: number | null;
  sos_trigger?: "double_click" | "long_press" | null;
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
  metadata?: Record<string, unknown>;
}

export interface FallReviewPendingMessage {
  type: "fall_alarm_pending_review";
  device_mac: string;
  incident_id: string;
  track_id?: string;
  title: string;
  lead: string;
  expected_seconds?: number;
  catalog_code?: string;
  presentation?: Record<string, unknown>;
  family_guidance?: Record<string, unknown>;
  event?: Record<string, unknown>;
}

export interface FallReviewFinalizedMessage {
  type: "fall_alarm_finalized";
  device_mac: string;
  incident_id: string;
  track_id?: string;
  catalog_code?: string;
  presentation?: Record<string, unknown>;
  family_guidance?: Record<string, unknown>;
  event?: Record<string, unknown>;
  review?: Record<string, unknown>;
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
  attachments?: AgentAttachment[];
  citations?: AgentCitation[];
  artifact_ids?: string[];
  scope?: AnalysisScope | "device";
  window?: WindowKind;
  subject?: Record<string, unknown> | null;
  mode?: string;
  selected_provider?: string;
  selected_model?: string;
  degraded?: string[];
}

export type CommunityWorkflow =
  | "overview"
  | "risk_ranking"
  | "alert_digest"
  | "device_focus"
  | "elder_focus"
  | "community_report"
  | "elder_report"
  | "report_generation"
  | "free_chat";
export type AgentAttachmentRenderType = "metric_cards" | "table" | "echarts" | "report_document";
export type AnalysisScope = "elder" | "community";
export type AgentProvider = "qwen" | "tongyi" | "ollama" | "auto";

export interface AgentAttachment {
  id: string;
  title: string;
  summary?: string;
  render_type: AgentAttachmentRenderType;
  render_payload: Record<string, unknown>;
  source_tool?: string;
}

export interface AgentCitation {
  id: string;
  title: string;
  source_path: string;
  chunk_id: string;
  snippet: string;
  score: number;
}

export interface AgentElderSubject {
  elder_id: string;
  elder_name: string;
  apartment: string;
  device_macs: string[];
  has_realtime_device: boolean;
  latest_timestamp?: string | null;
  risk_level: string;
  is_demo_subject: boolean;
}

export interface CommunityAnalysisPayload {
  question: string;
  role: string;
  mode: string;
  history_minutes?: number;
  per_device_limit?: number;
  device_macs?: string[];
  workflow?: CommunityWorkflow;
  focus_device_mac?: string;
  history?: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
  scope?: AnalysisScope;
  subject_elder_id?: string | null;
  window?: WindowKind;
  provider?: AgentProvider;
  include_report?: boolean;
}

export type AgentStreamEventType =
  | "session.started"
  | "stage.changed"
  | "trace.note"
  | "tool.started"
  | "tool.finished"
  | "answer.delta"
  | "answer.completed"
  | "session.completed"
  | "session.error";

export interface AgentStreamEventBase {
  type: AgentStreamEventType;
  timestamp?: string;
}

export interface AgentSessionStartedEvent extends AgentStreamEventBase {
  type: "session.started";
  session_id: string;
  scope: string;
  selected_model?: string;
  degraded_notes?: string[];
}

export interface AgentStageEvent extends AgentStreamEventBase {
  type: "stage.changed";
  stage: string;
  status: "running" | "completed" | "error";
  label?: string;
  detail?: string;
  summary?: string;
  elapsed_ms?: number | null;
  group?: "trace";
}

export interface AgentTraceEvent extends AgentStreamEventBase {
  type: "trace.note";
  stage: string;
  note: string;
  level?: "info" | "warning" | "error";
}

export interface AgentToolEvent extends AgentStreamEventBase {
  type: "tool.started" | "tool.finished";
  stage: string;
  tool_name: string;
  request_id: string;
  source?: string;
  status?: string;
  success?: boolean;
  summary?: string;
  error_message?: string | null;
  title?: string;
  tool_kind?: "data_query" | "analysis" | "report" | "recommendation";
  input_preview?: string;
  output_preview?: string;
  child_tools?: Array<{
    name: string;
    title?: string;
    summary?: string;
    status?: string;
  }>;
  render_type?: AgentAttachmentRenderType;
  render_payload?: Record<string, unknown>;
  attachments?: AgentAttachment[];
}

export interface AgentAnswerDeltaEvent extends AgentStreamEventBase {
  type: "answer.delta";
  session_id: string;
  delta: string;
}

export interface AgentAnswerCompletedEvent extends AgentStreamEventBase {
  type: "answer.completed";
  session_id: string;
  answer: string;
  references?: string[];
  analysis?: Record<string, unknown>;
  attachments?: AgentAttachment[];
  citations?: AgentCitation[];
  artifact_ids?: string[];
  scope?: AnalysisScope;
  window?: WindowKind;
  subject?: Record<string, unknown> | null;
}

export interface AgentSessionCompletedEvent extends AgentStreamEventBase {
  type: "session.completed";
  session_id: string;
  selected_model?: string;
  degraded_notes?: string[];
}

export interface AgentSessionErrorEvent extends AgentStreamEventBase {
  type: "session.error";
  session_id?: string;
  error: string;
}

export type AgentStreamEvent =
  | AgentSessionStartedEvent
  | AgentStageEvent
  | AgentTraceEvent
  | AgentToolEvent
  | AgentAnswerDeltaEvent
  | AgentAnswerCompletedEvent
  | AgentSessionCompletedEvent
  | AgentSessionErrorEvent;

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

export interface CommunityDashboardMetrics {
  elder_count: number;
  family_count: number;
  device_total: number;
  device_pending: number;
  device_online: number;
  device_offline: number;
  active_alarm_count: number;
  unacknowledged_alarm_count: number;
  sos_alarm_count: number;
  health_alert_count: number;
  device_alert_count: number;
  high_risk_elder_count: number;
  average_health_score: number;
  average_blood_oxygen: number;
  today_alarm_count: number;
  last_sync_at?: string | null;
}

export interface CommunityDashboardTrendPoint {
  timestamp: string;
  average_health_score: number;
  alert_count: number;
  high_risk_count: number;
}

export interface StructuredHealthInsight {
  evaluated_at?: string | null;
  health_score?: number | null;
  rule_health_score?: number | null;
  model_health_score?: number | null;
  risk_level?: string | null;
  abnormal_tags: string[];
  trigger_reasons: string[];
  active_event_count: number;
  recommendation_code?: string | null;
  score_adjustment_reason?: string | null;
}

export interface CommunityDashboardElderItem {
  elder_id: string;
  elder_name: string;
  apartment: string;
  device_mac?: string | null;
  family_names: string[];
  risk_level: "high" | "medium" | "low";
  risk_score: number;
  risk_reasons: string[];
  device_status: string;
  latest_timestamp?: string | null;
  latest_health_score?: number | null;
  heart_rate?: number | null;
  blood_oxygen?: number | null;
  blood_pressure?: string | null;
  temperature?: number | null;
  active_alarm_count: number;
  sos_active?: boolean;
  active_sos_alarm_id?: string | null;
  active_sos_trigger?: "double_click" | "long_press" | null;
  structured_health?: StructuredHealthInsight | null;
}

export interface CommunityDashboardDeviceItem {
  device_mac: string;
  device_name: string;
  model_code?: string | null;
  ingest_mode?: string | null;
  service_uuid?: string | null;
  device_uuid?: string | null;
  elder_id?: string | null;
  elder_name?: string | null;
  apartment?: string | null;
  device_status: string;
  activation_state?: string | null;
  bind_status: string;
  risk_level: "high" | "medium" | "low";
  risk_reasons: string[];
  latest_timestamp?: string | null;
  last_seen_at?: string | null;
  last_packet_type?: string | null;
  latest_health_score?: number | null;
  heart_rate?: number | null;
  blood_oxygen?: number | null;
  blood_pressure?: string | null;
  temperature?: number | null;
  battery?: number | null;
  steps?: number | null;
  active_alarm_count: number;
  sos_active?: boolean;
  active_sos_alarm_id?: string | null;
  active_sos_trigger?: "double_click" | "long_press" | null;
  structured_health?: StructuredHealthInsight | null;
}

export interface CommunityDashboardAlertItem {
  alarm_id: string;
  device_mac: string;
  elder_name?: string | null;
  apartment?: string | null;
  alarm_type: string;
  alarm_layer: string;
  alarm_level: number;
  message: string;
  created_at: string;
  acknowledged: boolean;
}

export interface RelationTopologyNode {
  id: string;
  kind: "community" | "elder" | "family" | "device";
  label: string;
  subtitle?: string | null;
  status?: string | null;
  risk_level?: string | null;
}

export interface RelationTopologyLane {
  elder: RelationTopologyNode;
  families: RelationTopologyNode[];
  devices: RelationTopologyNode[];
}

export interface CommunityRelationTopology {
  community: RelationTopologyNode;
  lanes: RelationTopologyLane[];
  unassigned_devices: RelationTopologyNode[];
}

export interface CommunityDashboardSummary {
  community: CommunityProfile;
  metrics: CommunityDashboardMetrics;
  top_risk_elders: CommunityDashboardElderItem[];
  device_statuses: CommunityDashboardDeviceItem[];
  recent_alerts: CommunityDashboardAlertItem[];
  trend: CommunityDashboardTrendPoint[];
  relation_topology?: CommunityRelationTopology | null;
}

export interface SystemInfoResponse {
  runtime_mode?: "mock" | "serial" | "mqtt";
  bootstrap_source?: string;
  bootstrap_status?: string;
  bootstrap_reason?: string;
  competition_stack: Record<string, unknown>;
  configured: Record<string, unknown>;
  serial_runtime?: {
    enabled: boolean;
    port: string;
    baudrate: number;
    collection_strategy?: string;
    packet_type: number;
    mac_filter: string;
    auto_configure: boolean;
    broadcast_sos_overlay: boolean;
    response_cycle_seconds: number;
    broadcast_cycle_seconds: number;
    active_target_mac?: string | null;
    active_target_device_name?: string | null;
    target_locked?: boolean;
    merge_mode?: string;
    runtime_mode?: string;
    bootstrap_source?: string;
    bootstrap_status?: string;
    bootstrap_reason?: string;
  };
  demo_data?: DemoDataStatus;
}

export interface DemoDataStatus {
  enabled: boolean;
  device_count: number;
  subject_count: number;
  latest_sample_at?: string | null;
  seed_profiles: string[];
}

export interface SerialTargetSwitchResponse {
  active_target_mac?: string | null;
  active_target_device_name?: string | null;
  previous_target_mac?: string | null;
  switched_at: string;
}

export interface ChatProviderCapability {
  chat_configured?: boolean;
  configured?: boolean;
  chat_model?: string;
  embedding_model?: string;
  rerank_model?: string;
  base_url?: string;
  model?: string;
}

export interface ChatRetrievalCapability {
  retrieval_mode: string;
  document_count: number;
  chunk_count: number;
  docs_hash: string;
  vector_enabled: boolean;
  bm25_enabled: boolean;
  rerank_enabled: boolean;
  embedding_model?: string;
  rerank_model?: string;
}

export interface AgentToolSpec {
  name: string;
  description: string;
  source?: string;
}

export interface ChatCapabilities {
  runtime: string;
  providers: {
    tongyi: ChatProviderCapability;
    ollama: ChatProviderCapability;
  };
  retrieval: ChatRetrievalCapability;
  analysis_tools: string[];
  tool_specs: AgentToolSpec[];
  extensions: {
    mcp_connected: boolean;
    demo_data?: DemoDataStatus;
  };
}

export type WindowKind = "day" | "week";
export type HistoryBucket = "raw" | "hour" | "day";

export interface SensorHistoryPoint {
  bucket_start: string;
  bucket_end?: string | null;
  heart_rate?: number | null;
  temperature?: number | null;
  blood_oxygen?: number | null;
  health_score?: number | null;
  battery?: number | null;
  steps?: number | null;
  sos_count: number;
  sample_count: number;
  risk_level?: string | null;
}

export interface DeviceHistoryResponse {
  device_mac: string;
  window: WindowKind;
  bucket: HistoryBucket;
  points: SensorHistoryPoint[];
}

export interface ChartPayload {
  id: string;
  title: string;
  type: string;
  echarts_option: Record<string, unknown>;
  summary: string;
}

export interface HighRiskEntity {
  device_mac: string;
  elder_name?: string | null;
  risk_level: string;
  latest_health_score?: number | null;
  active_alert_count: number;
  reasons: string[];
}

export interface CommunityWindowAnalysis {
  key_metrics: Record<string, unknown>;
  risk_distribution: Record<string, number>;
  alert_breakdown: Record<string, number>;
  device_status_distribution: Record<string, number>;
  high_risk_entities: HighRiskEntity[];
  trend_findings: string[];
  chart_payloads: ChartPayload[];
}

export interface CommunityWindowReportResponse {
  window: WindowKind;
  generated_at: string;
  analysis: CommunityWindowAnalysis;
}

export interface AgentSourceItem {
  source_type: string;
  title: string;
  url?: string | null;
  snippet: string;
}

export interface CommunityAgentMeta {
  llm_model: string;
  embedding_model: string;
  rerank_model: string;
  used_tavily: boolean;
  used_rerank: boolean;
  degraded_notes: string[];
}

export interface CommunityAgentSummaryResponse {
  window: WindowKind;
  generated_at: string;
  summary_text: string;
  advice: string[];
  analysis: CommunityWindowAnalysis;
  charts: ChartPayload[];
  sources: AgentSourceItem[];
  agent_meta: CommunityAgentMeta;
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

export interface CameraStatusResponse {
  configured: boolean;
  online: boolean;
  ip: string;
  port: number;
  path: string;
  checked_at: string;
  latency_ms?: number | null;
  error?: string | null;
  source?: "rtsp" | "local";
  detail?: string | null;
}

export interface CameraSourceRecord {
  camera_id: string;
  name: string;
  enabled: boolean;
  source: string;
  source_mode: "local" | "rtsp";
  device_id?: string;
  ip?: string;
  rtsp_port?: number;
  onvif_port?: number;
  rtsp_path?: string;
  stream_rtsp_path?: string;
  audio_rtsp_path?: string;
  has_password?: boolean;
}

export interface CameraSourceRegistrationResponse {
  active_camera_id: string;
  active_source: CameraSourceRecord;
  sources: CameraSourceRecord[];
  registry_path?: string;
}

export interface ExternalCameraTruthRecord {
  camera_id?: string;
  preferred_host?: string;
  host?: string;
  username?: string;
  rtsp_port?: number;
  transport?: string;
  stream?: string;
  verified_at?: string | null;
  verified_status?: string;
  verification_reason?: string | null;
  source_of_truth?: string;
  fallback_order?: Array<Record<string, unknown>>;
}

export interface ExternalCameraConfigResponse {
  config: Record<string, unknown>;
  truth?: ExternalCameraTruthRecord;
  camera_health?: ExternalCameraHealthResponse;
  viewer_url?: string;
  snapshot_url?: string;
  mjpeg_url?: string;
  runtime_root?: string;
  rtsp_source?: string;
  rtsp_host?: string;
  rtsp_stream?: string;
}

export interface ExternalCameraBootstrapResponse {
  ok: boolean;
  status: string;
  camera_health?: ExternalCameraHealthResponse;
  truth?: ExternalCameraTruthRecord;
  probe?: Record<string, unknown>;
  bridge_latency_ms?: number;
}

export type CameraPtzDirection =
  | "up"
  | "down"
  | "left"
  | "right"
  | "up_left"
  | "up_right"
  | "down_left"
  | "down_right"
  | "zoom_in"
  | "zoom_out"
  | "stop";

export interface CameraPtzResponse {
  ok: boolean;
  direction: CameraPtzDirection;
  mode?: "pulse" | "continuous";
}

export interface CameraStreamStatusResponse {
  clients: number;
  websocket_clients?: number;
  mjpeg_clients?: number;
  running: boolean;
  keep_warm?: boolean;
  latest_frame_at?: number | null;
  latest_frame_size?: number;
  last_error?: string | null;
  frames_total?: number;
  broadcast_total?: number;
  target_fps?: number;
  source_fps?: number;
  broadcast_fps?: number;
  measured_fps?: number;
  active_url?: string | null;
  profile?: "smooth" | "balanced" | "quality";
  jpeg_quality?: number;
  stream_width?: number;
}

export type VideoBridgeServiceState = "mock" | "starting" | "running" | "degraded" | "stopped" | "error" | "unknown";
export type VideoBridgeFallState = "unknown" | "normal" | "suspected_fall" | "confirmed_fall" | "fallen" | "recovery" | "error";
export type VideoBridgeRisk = "unknown" | "low" | "medium" | "high" | "critical";

export interface VideoBridgeTarget {
  target_id?: string | null;
  label?: string | null;
  matched?: boolean | null;
  confidence?: number | null;
  metadata?: Record<string, unknown>;
}

export interface VideoBridgeAnalysisRecord {
  camera_id: string;
  stream_name: string;
  service_state: VideoBridgeServiceState;
  camera_lost: boolean;
  capture_stale: boolean;
  frame_age_ms?: number | null;
  video_fps?: number | null;
  overlay_fps?: number | null;
  ws_fps?: number | null;
  track_id?: string | null;
  bbox?: number[] | null;
  target?: VideoBridgeTarget | Record<string, unknown> | string | null;
  fall_state: VideoBridgeFallState;
  risk: VideoBridgeRisk;
  fall_prob?: number | null;
  snapshot_url?: string | null;
  timestamp: string;
  metadata: Record<string, unknown>;
  received_at: string;
  stale: boolean;
  adapter_version: string;
}

export interface VideoBridgeStatusResponse {
  ok: boolean;
  bridge_state: VideoBridgeServiceState;
  adapter_version: string;
  camera_count: number;
  updated_at: string;
  latest?: VideoBridgeAnalysisRecord | null;
  cameras: VideoBridgeAnalysisRecord[];
  notes: string[];
  vision_service?: {
    enabled?: boolean;
    base_url?: string;
    camera_id?: string;
    poll_hz?: number;
    last_poll_at?: string | null;
    last_ok_at?: string | null;
    last_error?: string | null;
    health?: unknown;
    source?: unknown;
    latest_received_at?: string | null;
  };
}

export interface VideoBridgeIngestResponse {
  ok: boolean;
  accepted: boolean;
  camera_id: string;
  stream_name: string;
  received_at: string;
  service_state: VideoBridgeServiceState;
  stale: boolean;
}

export interface VideoBridgeFallAlarmSimulationResponse {
  ok: boolean;
  accepted: boolean;
  alarm: AlarmRecord;
  camera_id: string;
  stream_name: string;
  risk: VideoBridgeRisk;
  fall_prob: number;
  snapshot_url: string;
  triggered_at: string;
  elder_id?: string;
  elder_name?: string;
}

export interface CameraAudioStatusResponse {
  configured: boolean;
  listen_supported: boolean;
  talk_supported: boolean;
  checked_url?: string | null;
  audio_codec?: string | null;
  sample_rate?: number | null;
  channels?: number | null;
  source?: "rtsp" | "local";
  sdk_available?: boolean;
  sdk_arch?: string | null;
  sdk_loadable?: boolean;
  sdk_message?: string | null;
  gateway_configured?: boolean;
  activex_available?: boolean;
  activex_clsid?: string | null;
  activex_inproc_path?: string | null;
  activex_message?: string | null;
  error?: string | null;
}

export interface CameraAudioStreamStatusResponse {
  clients: number;
  running: boolean;
  last_error?: string | null;
  active_url?: string | null;
  sample_rate?: number;
  format?: string;
  channels?: number;
  chunks_total?: number;
  bytes_total?: number;
  kbps?: number;
}

export interface CameraFallDetectionStatusResponse {
  enabled: boolean;
  running: boolean;
  process_running: boolean;
  pid?: number | null;
  speed_profile?: "accuracy" | "balanced" | "fast";
  accuracy_preserving?: boolean;
  event_log?: string;
  snapshot_dir?: string;
  roi?: {
    enabled?: boolean;
    rect?: string;
    min_overlap?: number;
    frame_width?: number;
    frame_height?: number;
    min_alert_score?: number;
  };
  last_event_at?: number | null;
  last_event?: Record<string, unknown> | null;
  last_error?: string | null;
  restart_count?: number;
  started_at?: number | null;
  multimodal_review?: {
    enabled: boolean;
    configured_provider: string;
    resolved_provider: string;
    dashscope_configured: boolean;
    qwen_omni_model?: string | null;
    siliconflow_configured: boolean;
    min_score: number;
    timeout_seconds: number;
  };
}

export interface PoseTrackPayload {
  track_id: number;
  bbox: number[];
  pose_score: number;
  state_label: string;
  state_score: number;
  keypoints: number[][];
  features?: Record<string, number>;
}

export interface CameraPoseDetectionLatestResponse {
  backend?: string;
  profile?: string;
  source?: string;
  timestamp_s?: number;
  frame_idx?: number;
  frame_width?: number;
  frame_height?: number;
  tracks: PoseTrackPayload[];
  _observed_at?: number;
  status?: string;
}

export interface CameraPoseDetectionStatusResponse {
  enabled: boolean;
  running: boolean;
  process_running: boolean;
  pid?: number | null;
  profile?: string;
  process_every_override?: number;
  pose_conf_threshold?: number;
  analysis_width?: number;
  event_log?: string;
  latest_json?: string;
  snapshot_dir?: string;
  source_mode?: "auto" | "rtsp" | "local";
  source_url?: string;
  model_root?: string;
  model_root_exists?: boolean;
  python_command?: string;
  python_exists?: boolean | null;
  last_payload_at?: number | null;
  last_payload?: CameraPoseDetectionLatestResponse | null;
  last_error?: string | null;
  restart_count?: number;
  started_at?: number | null;
}

export interface CameraPoseDetectionConfigResponse {
  enabled: boolean;
  profile: string;
  process_every_override: number;
  pose_conf_threshold: number;
  analysis_width: number;
  floor_roi_rect: string;
}

export interface TargetUserRecord {
  id: string;
  display_name: string;
  group: string;
  note: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  photo_count: number;
  face_embedding_count: number;
  body_profile_count: number;
}

export interface ExternalCameraHealthResponse {
  running: boolean;
  source: string;
  stream: string;
  transport: string;
  rtsp_port: number;
  has_frame: boolean;
  bridge_status?: string;
  fresh_frame?: boolean;
  stale_frame?: boolean;
  frame_age_seconds?: number | null;
  latest_frame_at?: number | null;
  frame_count?: number;
  last_error?: string | null;
  last_opened_at?: number | null;
  reconnect_count?: number;
  consecutive_failures?: number;
  current_stream?: string | null;
  bridge_latency_ms?: number;
  rtsp_host?: string;
  rtsp_stream?: string;
  truth?: ExternalCameraTruthRecord;
  candidate_runtime?: Record<string, unknown>;
  viewer_url?: string;
  snapshot_url?: string;
  mjpeg_url?: string;
}

export interface ExternalCameraFallDetectResponse {
  ok: boolean;
  status: string;
  target_match?: {
    matched: boolean;
    user_id?: string | null;
    display_name?: string | null;
    face_score?: number;
    body_score?: number;
    fused_score?: number;
    decision?: "target" | "non_target" | "unknown";
  } | null;
  fall_result?: {
    ok?: boolean;
    status?: string;
    fall_detected?: boolean;
    fall_score?: number;
    scores?: Record<string, number>;
    detections?: Array<Record<string, unknown>>;
    alert?: Record<string, unknown>;
    annotated_image_b64?: string;
    annotated_image_mime?: string;
    frame?: {
      width: number;
      height: number;
    } | null;
    error?: string;
  } | null;
  warnings?: string[];
  tracking?: {
    session_id?: string;
    track_id?: number | null;
    used_track?: boolean;
    full_match_refreshed?: boolean;
    candidate_count?: number;
    roi?: {
      bbox?: number[] | null;
      used_roi?: boolean;
    } | null;
  } | null;
  diagnostics?: {
    is_failure?: boolean;
    reasons?: string[];
    warnings?: string[];
    candidate_count?: number;
    track_id?: number | null;
    used_track?: boolean;
    used_roi?: boolean;
    match_decision?: string;
    face_score?: number;
    body_score?: number;
    fused_score?: number;
    fall_status?: string;
  } | null;
  camera_source?: {
    viewer_url?: string;
    snapshot_url?: string;
    mjpeg_url?: string;
  } | null;
  target_pose?: {
    ok?: boolean;
    error?: string;
    pose?: {
      points?: Array<{
        index: number;
        name: string;
        x: number;
        y: number;
        score: number;
        tracked?: boolean;
        estimated?: boolean;
      }>;
      connections?: Array<{
        from: number;
        to: number;
        part: string;
      }>;
      posture?: {
        label?: string;
        severity?: string;
        confidence?: number;
        torso_angle_deg?: number | null;
        features?: Record<string, unknown>;
      };
      quality?: {
        visible_points?: number;
        mean_score?: number;
        estimated_points?: number;
      };
    };
    latency_ms?: number;
    model?: Record<string, unknown>;
  } | null;
  posture_event?: {
    type?: string;
    level?: string;
    confidence?: number;
    source_pose?: string;
    reasons?: string[];
    metrics?: Record<string, unknown>;
    timestamp_ms?: number;
  } | null;
  posture_guidance?: {
    level?: string;
    title?: string;
    possible_causes?: string[];
    immediate_actions?: string[];
    contraindications?: string[];
    call_emergency?: boolean;
  } | null;
  bridge_latency_ms?: number;
  latency_ms?: number;
  snapshot_bytes?: number;
}

export interface TargetUserCreateResponse {
  user: TargetUserRecord;
  warnings: string[];
}

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:18080/api/v1";

function deriveWsBase() {
  const rawWsBase = (import.meta.env.VITE_WS_BASE ?? "").trim();
  const rawApiBase = API_BASE.trim();

  const looksInvalidPlaceholder = (value: string) =>
    !value
    || value.includes("<URL>")
    || value.includes("${")
    || value.includes("undefined")
    || value.includes("null");

  if (!looksInvalidPlaceholder(rawWsBase)) {
    return rawWsBase.replace(/\/$/, "");
  }

  if (!looksInvalidPlaceholder(rawApiBase)) {
    return rawApiBase.replace(/^http/i, "ws").replace(/\/api\/v1\/?$/i, "").replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    return window.location.origin.replace(/^http/i, "ws").replace(/\/$/, "");
  }

  return "ws://127.0.0.1:18080";
}

const WS_BASE = deriveWsBase();

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

type RequestJsonOptions = {
  timeoutMs?: number;
  allowEmptyResponse?: boolean;
};

function humanizeApiDetail(detail: string): string {
  if (detail.includes("INVALID_MAC_ADDRESS")) return "设备 MAC 格式错误，请使用 AA:BB:CC:DD:EE:FF。";
  if (detail.includes("INVALID_MAC_PREFIX")) return "当前服务尚未完成更新，请刷新页面或重启后端后重试。";
  if (detail.includes("DEVICE_ALREADY_EXISTS")) return "该设备已经登记在台账中。";
  if (detail.includes("TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL")) {
    return "该老人已经绑定了同型号手环。若本次只是演示新设备，请选择“暂不绑定，先登记设备”。";
  }
  if (detail.includes("REQUEST_TIMEOUT")) return "服务响应超时，请确认后端已启动后重试。";
  if (detail.includes("NETWORK_UNAVAILABLE")) return "无法连接到后端服务，请确认后端已启动。";
  return detail;
}

async function requestJson<T>(url: string, init?: RequestInit, options: RequestJsonOptions = {}): Promise<T> {
  const controller = options.timeoutMs ? new AbortController() : null;
  const timeoutId = controller
    ? window.setTimeout(() => {
        controller.abort();
      }, options.timeoutMs)
    : null;

  try {
    const response = await fetch(url, {
      ...init,
      signal: controller?.signal ?? init?.signal,
    });

    if (response.status === 204 && options.allowEmptyResponse) {
      return null as T;
    }

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
          detail = humanizeApiDetail(detailPayload);
        } else if (Array.isArray(detailPayload) && detailPayload.length) {
          const first = detailPayload[0];
          const message = String(first.msg ?? "");
          if (message.includes("INVALID_MAC_ADDRESS")) detail = "设备 MAC 格式错误，请使用 AA:BB:CC:DD:EE:FF。";
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
  } catch (error) {
    if (error instanceof ApiError) throw error;

    const isAbortError = error instanceof Error && error.name === "AbortError";
    const timedOut = Boolean(controller?.signal.aborted && !init?.signal?.aborted);

    if (isAbortError && timedOut) {
      throw new ApiError(408, humanizeApiDetail("REQUEST_TIMEOUT"));
    }

    if (isAbortError) {
      throw error;
    }

    throw new ApiError(503, humanizeApiDetail("NETWORK_UNAVAILABLE"));
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
  }
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

async function throwApiError(response: Response): Promise<never> {
  let detail = `Request failed: ${response.status}`;
  try {
    const payload = (await response.json()) as {
      detail?: string | { message?: string; code?: string };
    };
    if (typeof payload.detail === "string") {
      detail = humanizeApiDetail(payload.detail);
    } else if (payload.detail?.message) {
      detail = humanizeApiDetail(payload.detail.message);
    } else if (payload.detail?.code) {
      detail = humanizeApiDetail(payload.detail.code);
    }
  } catch {
    // ignore non-json errors
  }
  throw new ApiError(response.status, detail);
}

export async function streamCommunityAnalysis(
  payload: CommunityAnalysisPayload,
  handlers: {
    signal?: AbortSignal;
    onEvent?: (event: AgentStreamEvent) => void;
  } = {},
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/analyze/community/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  if (!response.body) {
    throw new ApiError(500, "Stream body is not available");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n");
      buffer = chunks.pop() ?? "";

      for (const line of chunks) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const event = JSON.parse(trimmed) as AgentStreamEvent;
        handlers.onEvent?.(event);
      }
    }

    const tail = `${buffer}${decoder.decode()}`.trim();
    if (tail) {
      handlers.onEvent?.(JSON.parse(tail) as AgentStreamEvent);
    }
  } finally {
    reader.releaseLock();
  }
}

export const api = {
  getCameraStatus: () => requestJson<CameraStatusResponse>(`${API_BASE}/camera/status`),
  getCameraStreamStatus: () => requestJson<CameraStreamStatusResponse>(`${API_BASE}/camera/stream-status`),
  getCameraAudioStatus: () => requestJson<CameraAudioStatusResponse>(`${API_BASE}/camera/audio/status`),
  getCameraAudioStreamStatus: () =>
    requestJson<CameraAudioStreamStatusResponse>(`${API_BASE}/camera/audio/stream-status`),
  getCameraFallDetectionStatus: () =>
    requestJson<CameraFallDetectionStatusResponse>(`${API_BASE}/camera/fall-detection/status`),
  getCameraPoseDetectionStatus: () =>
    requestJson<CameraPoseDetectionStatusResponse>(`${API_BASE}/camera/pose-detection/status`),
  getCameraPoseDetectionLatest: () =>
    requestJson<CameraPoseDetectionLatestResponse>(`${API_BASE}/camera/pose-detection/latest`),
  getCameraPoseDetectionConfig: () =>
    requestJson<CameraPoseDetectionConfigResponse>(`${API_BASE}/camera/pose-detection/config`),
  updateCameraPoseDetectionConfig: (payload: {
    pose_detection_enabled?: boolean;
    pose_detection_profile?: string;
    pose_detection_process_every_override?: number;
    pose_detection_pose_conf_threshold?: number;
    pose_detection_analysis_width?: number;
    pose_detection_floor_roi_rect?: string;
  }) =>
    requestJson<{ ok: boolean; config: CameraPoseDetectionConfigResponse; restarted: boolean }>(
      `${API_BASE}/camera/pose-detection/config`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
      { timeoutMs: 20000 },
    ),
  getCameraFallSnapshotUrl: (path: string) => {
    const normalized = path.trim();
    if (/^https?:\/\//i.test(normalized)) return normalized;
    if (normalized.startsWith("/api/v1/")) return `${API_BASE.replace(/\/api\/v1\/?$/i, "")}${normalized}`;
    if (normalized.startsWith("/")) return normalized;
    return `${API_BASE}/camera/fall-detection/snapshot?path=${encodeURIComponent(normalized)}&t=${Date.now()}`;
  },
  getCameraSnapshotUrl: () => `${API_BASE}/camera/snapshot?t=${Date.now()}`,
  getCameraStreamUrl: () => `${API_BASE}/camera/stream.mjpg?t=${Date.now()}`,
  getCameraDetectionStreamUrl: () => `${API_BASE}/camera/stream.detect.mjpg?t=${Date.now()}`,
  getCameraPoseStreamUrl: () => `${API_BASE}/camera/stream.pose.mjpg?t=${Date.now()}`,
  getCameraProcessedStreamUrl: () => `${API_BASE}/camera/stream.processed.mjpg?t=${Date.now()}`,
  getVideoBridgeStatus: () => requestJson<VideoBridgeStatusResponse>(`${API_BASE}/video-bridge/status`),
  pollVideoBridgeVisionOnce: () =>
    requestJson<Record<string, unknown>>(`${API_BASE}/video-bridge/vision/poll-once`, { method: "POST" }),
  probeVideoBridgeVisionStream: (payload: { host: string; port?: number; timeout_ms?: number }) =>
    requestJson<Record<string, unknown>>(`${API_BASE}/video-bridge/vision/probe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, { timeoutMs: 10000 }),
  switchVideoBridgeVisionHost: (payload: {
    camera_id?: string;
    host: string;
    username?: string;
    password?: string;
    port?: number;
    main_path?: string;
    analysis_path?: string;
  }) =>
    requestJson<Record<string, unknown>>(`${API_BASE}/video-bridge/vision/switch-host`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, { timeoutMs: 15000 }),
  pushVideoBridgeAnalysis: (payload: Partial<VideoBridgeAnalysisRecord> & { camera_id: string }) =>
    requestJson<VideoBridgeIngestResponse>(`${API_BASE}/video-bridge/analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  simulateVideoBridgeFallAlarm: (payload?: {
    camera_id?: string;
    stream_name?: string;
    fall_prob?: number;
    snapshot_url?: string;
    track_id?: string;
  }) =>
    requestJson<VideoBridgeFallAlarmSimulationResponse>(`${API_BASE}/video-bridge/simulate-fall-alarm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    }),
  cameraFrameSocket: () => new WebSocket(`${WS_BASE}/ws/camera`),
  cameraAudioSocket: () => new WebSocket(`${WS_BASE}/ws/camera/audio/listen`),
  getCameraSourceRegistration: () =>
    requestJson<CameraSourceRegistrationResponse>(`${API_BASE}/camera-sources/registration`),
  registerExternalCameraSource: (payload: { device_id: string; name?: string }) =>
    requestJson<CameraSourceRegistrationResponse>(`${API_BASE}/camera-sources/registration/external`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  selectLocalCameraSource: () =>
    requestJson<CameraSourceRegistrationResponse>(`${API_BASE}/camera-sources/registration/local/select`, {
      method: "POST",
    }),
  selectCameraSource: (camera_id: string) =>
    requestJson<CameraSourceRegistrationResponse>(`${API_BASE}/camera-sources/registration/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id }),
    }),
  getActiveCameraStatus: () => requestJson<CameraStatusResponse>(`${API_BASE}/camera-sources/active/status`),
  getActiveCameraStreamStatus: () =>
    requestJson<CameraStreamStatusResponse>(`${API_BASE}/camera-sources/active/stream-status`),
  getActiveCameraAudioStatus: () =>
    requestJson<CameraAudioStatusResponse>(`${API_BASE}/camera-sources/active/audio/status`),
  getActiveCameraAudioStreamStatus: () =>
    requestJson<CameraAudioStreamStatusResponse>(`${API_BASE}/camera-sources/active/audio/stream-status`),
  getActiveCameraStreamUrl: () => `${API_BASE}/camera-sources/active/stream.mjpg?t=${Date.now()}`,
  getActiveCameraSnapshotUrl: () => `${API_BASE}/camera-sources/active/snapshot?t=${Date.now()}`,
  activeCameraFrameSocket: () => new WebSocket(`${WS_BASE}/ws/camera-sources/active`),
  activeCameraAudioSocket: () => new WebSocket(`${WS_BASE}/ws/camera-sources/active/audio/listen`),
  moveActiveCamera: (direction: CameraPtzDirection, mode: "pulse" | "continuous" = "pulse") =>
    requestJson<CameraPtzResponse>(`${API_BASE}/camera-sources/active/ptz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction, mode }),
    }),
  moveCamera: (direction: CameraPtzDirection, mode: "pulse" | "continuous" = "pulse") =>
    requestJson<CameraPtzResponse>(`${API_BASE}/camera/ptz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction, mode }),
    }),
  listTargetUsers: () => requestJson<TargetUserRecord[]>(`${API_BASE}/target-users`),
  createTargetUser: async (payload: {
    display_name: string;
    group?: string;
    note?: string;
    files: File[];
  }) => {
    const form = new FormData();
    form.append("display_name", payload.display_name);
    form.append("group", payload.group ?? "default");
    form.append("note", payload.note ?? "");
    for (const file of payload.files) {
      form.append("files", file);
    }
    const response = await fetch(`${API_BASE}/target-users`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      let detail = `Request failed: ${response.status}`;
      try {
        const payload = (await response.json()) as { detail?: string };
        if (typeof payload.detail === "string") detail = humanizeApiDetail(payload.detail);
      } catch {
        // ignore
      }
      throw new ApiError(response.status, detail);
    }
    return response.json() as Promise<TargetUserCreateResponse>;
  },
  deleteTargetUser: (userId: string) =>
    requestJson<{ ok: boolean; id: string }>(`${API_BASE}/target-users/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }),
  getExternalCameraHealth: () =>
    requestJson<ExternalCameraHealthResponse>(`${API_BASE}/target-users/external-camera/health`),
  getExternalCameraConfig: () =>
    requestJson<ExternalCameraConfigResponse>(`${API_BASE}/target-users/external-camera/config`),
  bootstrapExternalCamera: () =>
    requestJson<ExternalCameraBootstrapResponse>(`${API_BASE}/target-users/external-camera/bootstrap`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force: true }),
    }),
  probeExternalCameraRuntime: (payload: {
    host?: string;
    username?: string;
    password?: string;
    rtsp_port?: number;
    transport?: string;
    stream?: string;
    apply_success?: boolean;
  }) =>
    requestJson<Record<string, unknown>>(`${API_BASE}/target-users/external-camera/probe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, { timeoutMs: 40000 }),
  discoverExternalCameraCandidates: (subnet?: string, limit = 64) => {
    const params = new URLSearchParams();
    if (subnet) params.set("subnet", subnet);
    params.set("limit", String(limit));
    return requestJson<Record<string, unknown>>(
      `${API_BASE}/target-users/external-camera/discover?${params.toString()}`,
      undefined,
      { timeoutMs: 40000 },
    );
  },
  refreshExternalCameraRuntime: (prefer_stream?: string) => {
    const params = new URLSearchParams();
    if (prefer_stream) params.set("prefer_stream", prefer_stream);
    const suffix = params.toString();
    return requestJson<Record<string, unknown>>(
      `${API_BASE}/target-users/external-camera/refresh${suffix ? `?${suffix}` : ""}`,
      { method: "POST" },
      { timeoutMs: 20000 },
    );
  },
  runExternalCameraFallDetect: (payload?: {
    target_only?: boolean;
    session_id?: string;
    mode?: "metadata" | "annotated";
  }) => {
    const params = new URLSearchParams();
    params.set("target_only", String(payload?.target_only ?? true));
    params.set("session_id", payload?.session_id ?? "default");
    params.set("mode", payload?.mode ?? "metadata");
    return requestJson<ExternalCameraFallDetectResponse>(
      `${API_BASE}/target-users/external-camera/fall-detect?${params.toString()}`,
      { method: "POST" },
      { timeoutMs: 30000 },
    );
  },
  getLocalCameraSnapshotUrl: () => `${API_BASE}/target-users/local-camera/snapshot?t=${Date.now()}`,
  runLocalCameraPoseDetect: (payload?: {
    target_only?: boolean;
    session_id?: string;
    mode?: "metadata" | "annotated";
  }) => {
    const params = new URLSearchParams();
    params.set("target_only", String(payload?.target_only ?? true));
    params.set("session_id", payload?.session_id ?? "default");
    params.set("mode", payload?.mode ?? "metadata");
    return requestJson<ExternalCameraFallDetectResponse>(
      `${API_BASE}/target-users/local-camera/pose-detect?${params.toString()}`,
      { method: "POST" },
      { timeoutMs: 30000 },
    );
  },
  runBrowserFrameTargetPoseDetect: async (
    file: Blob,
    payload?: {
      target_only?: boolean;
      session_id?: string;
      mode?: "metadata" | "annotated";
      speed_mode?: string;
    },
  ) => {
    const params = new URLSearchParams();
    params.set("target_only", String(payload?.target_only ?? true));
    params.set("session_id", payload?.session_id ?? "browser-preview");
    params.set("mode", payload?.mode ?? "annotated");
    params.set("speed_mode", payload?.speed_mode ?? "balanced");
    const form = new FormData();
    form.append("file", file, "browser_camera_frame.jpg");
    const response = await fetch(`${API_BASE}/target-users/fall-detect?${params.toString()}`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      let detail = `Request failed: ${response.status}`;
      try {
        const payload = (await response.json()) as { detail?: string };
        if (typeof payload.detail === "string") detail = humanizeApiDetail(payload.detail);
      } catch {
        // ignore
      }
      throw new ApiError(response.status, detail);
    }
    return response.json() as Promise<ExternalCameraFallDetectResponse>;
  },
  listDevices: () => requestJson<DeviceRecord[]>(`${API_BASE}/devices`),
  getDevice: (mac: string) => requestJson<DeviceRecord>(`${API_BASE}/devices/${mac}`),
  registerDevice: (
    payload: {
      mac_address: string;
      device_name?: string;
      user_id?: string | null;
      model_code?: string;
      ingest_mode?: "serial" | "mqtt" | "ble" | "mock";
      service_uuid?: string;
      device_uuid?: string;
    },
    token?: string,
  ) =>
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
  switchSerialTarget: (payload: { mac_address: string }, token?: string) =>
    requestJson<SerialTargetSwitchResponse>(`${API_BASE}/devices/serial-target`, {
      method: "POST",
      headers: jsonHeaders(token),
      body: JSON.stringify(payload),
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
  getRealtime: (mac: string) =>
    requestJson<HealthSample | null>(`${API_BASE}/health/realtime/${mac}`, undefined, { allowEmptyResponse: true }),
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
  ackActiveFallAlarms: () =>
    requestJson<{ acknowledged_count: number; alarm_ids: string[] }>(
      `${API_BASE}/alarms/fall/acknowledge-active`,
      { method: "POST" },
    ),
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
  analyzeCommunity: (payload: CommunityAnalysisPayload) =>
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
  listMockAccounts: (options?: RequestJsonOptions) =>
    requestJson<AuthAccountPreview[]>(`${API_BASE}/auth/mock-accounts`, undefined, options),
  login: (payload: { username: string; password: string }, options?: RequestJsonOptions) =>
    requestJson<LoginResponse>(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, options),
  loginMock: (payload: { username: string; password: string }, options?: RequestJsonOptions) =>
    requestJson<LoginResponse>(`${API_BASE}/auth/mock-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, options),
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
  me: (token: string, options?: RequestJsonOptions) =>
    requestJson<SessionUser>(`${API_BASE}/auth/me`, {
      headers: withBearer(token),
    }, options),
  getSystemInfo: () => requestJson<SystemInfoResponse>(`${API_BASE}/system/info`),
  getDemoDataStatus: () => requestJson<DemoDataStatus>(`${API_BASE}/system/demo-data/status`),
  refreshDemoData: () =>
    requestJson<{ status: string; message: string; data: DemoDataStatus }>(`${API_BASE}/system/demo-data/refresh`, {
      method: "POST",
    }),
  getChatCapabilities: () => requestJson<ChatCapabilities>(`${API_BASE}/chat/capabilities`),
  getCareAccessProfile: (token: string) =>
    requestJson<CareAccessProfile>(`${API_BASE}/care/access-profile/me`, {
      headers: withBearer(token),
    }),
  getCommunityDashboard: (token: string) =>
    requestJson<CommunityDashboardSummary>(`${API_BASE}/care/community/dashboard`, {
      headers: withBearer(token),
    }),
  getDeviceHistory: (mac: string, window: WindowKind = "day", bucket?: HistoryBucket) =>
    requestJson<DeviceHistoryResponse>(
      `${API_BASE}/health/devices/${mac}/history?window=${window}${bucket ? `&bucket=${bucket}` : ""}`,
    ),
  getCommunityWindowReport: (payload: { window: WindowKind; device_macs?: string[] }) =>
    requestJson<CommunityWindowReportResponse>(`${API_BASE}/health/community/window-report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  exportCommunityWindowReport: (window: WindowKind = "day", deviceMacs?: string[]) =>
    requestJson<CommunityWindowReportResponse>(
      `${API_BASE}/health/community/window-report/export?window=${window}${
        deviceMacs?.length ? `&${deviceMacs.map((item) => `device_macs=${encodeURIComponent(item)}`).join("&")}` : ""
      }`,
    ),
  getCommunityAgentSummary: (payload: {
    window: WindowKind;
    question: string;
    device_macs?: string[];
    include_web_search?: boolean;
    include_charts?: boolean;
  }) =>
    requestJson<CommunityAgentSummaryResponse>(`${API_BASE}/agent/community/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getAgentElders: (token: string) =>
    requestJson<AgentElderSubject[]>(`${API_BASE}/agent/elders`, {
      headers: withBearer(token),
    }),
  healthSocket: (mac: string) => new WebSocket(`${WS_BASE}/ws/health/${mac}`),
  alarmSocket: (token?: string) => {
    const resolvedToken = token?.trim() ?? "";
    const url = resolvedToken
      ? `${WS_BASE}/ws/alarms?token=${encodeURIComponent(resolvedToken)}`
      : `${WS_BASE}/ws/alarms`;
    return new WebSocket(url);
  },

  // Voice API
  voiceStatus: () =>
    requestJson<{
      configured: boolean;
      asr_model: string | null;
      tts_model: string | null;
      tts_voices: string[];
      provider?: string;
      service_provider?: string;
      note: string;
    }>(`${API_BASE}/voice/status`).then((payload) => ({
      ...payload,
      provider: payload.provider ?? payload.service_provider ?? "none",
    })),
  voiceAsr: async (audioBlob: Blob): Promise<{ ok: boolean; text: string; provider: string; error?: string }> => {
    const form = new FormData();
    form.append("file", audioBlob, "recording.wav");
    const res = await fetch(`${API_BASE}/voice/asr`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`ASR HTTP ${res.status}`);
    return res.json();
  },
  voiceTts: (text: string, voice = "longyingtian", fmt: "mp3" | "wav" = "mp3") =>
    requestJson<{ ok: boolean; audio_b64: string; fmt: string; provider: string; error?: string }>(`${API_BASE}/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice, fmt }),
    }),
};
