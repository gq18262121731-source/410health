CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL,
    role VARCHAR(24) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mac_address VARCHAR(32) NOT NULL UNIQUE,
    device_name VARCHAR(64) NOT NULL,
    model_code VARCHAR(32) NOT NULL DEFAULT 't10_v3',
    ingest_mode VARCHAR(24) NOT NULL DEFAULT 'serial',
    service_uuid VARCHAR(64) NOT NULL DEFAULT '',
    device_uuid VARCHAR(64) NOT NULL DEFAULT '',
    user_id UUID REFERENCES users(id),
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    activation_state VARCHAR(24) NOT NULL DEFAULT 'pending',
    bind_status VARCHAR(24) NOT NULL DEFAULT 'unbound',
    last_seen_at TIMESTAMPTZ,
    last_packet_type VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS family_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elder_user_id UUID NOT NULL REFERENCES users(id),
    family_user_id UUID NOT NULL REFERENCES users(id),
    relation_type VARCHAR(32) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (elder_user_id, family_user_id)
);

CREATE TABLE IF NOT EXISTS device_bind_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID NOT NULL REFERENCES devices(id),
    old_user_id UUID REFERENCES users(id),
    new_user_id UUID REFERENCES users(id),
    action_type VARCHAR(24) NOT NULL,
    operator_id UUID REFERENCES users(id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS health_data (
    id BIGSERIAL PRIMARY KEY,
    device_mac VARCHAR(32) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    heart_rate INTEGER NOT NULL,
    temperature NUMERIC(4,1) NOT NULL,
    blood_oxygen INTEGER NOT NULL,
    blood_pressure VARCHAR(16) NOT NULL,
    battery INTEGER NOT NULL,
    sos_flag BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('health_data', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_health_data_device_time ON health_data(device_mac, timestamp DESC);

CREATE TABLE IF NOT EXISTS alarms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_mac VARCHAR(32) NOT NULL,
    alarm_type VARCHAR(32) NOT NULL,
    alarm_level INTEGER NOT NULL,
    message TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sensor_samples (
    id BIGSERIAL PRIMARY KEY,
    device_mac VARCHAR(32) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    heart_rate INTEGER NOT NULL,
    temperature NUMERIC(4,1) NOT NULL,
    blood_oxygen INTEGER NOT NULL,
    blood_pressure VARCHAR(16),
    battery INTEGER NOT NULL,
    steps INTEGER,
    sos_flag BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR(24) NOT NULL,
    device_uuid TEXT,
    ambient_temperature NUMERIC(4,1),
    surface_temperature NUMERIC(4,1),
    packet_type VARCHAR(32),
    raw_packet_a TEXT,
    raw_packet_b TEXT,
    anomaly_score NUMERIC(8,4),
    health_score INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('sensor_samples', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_sensor_samples_device_time ON sensor_samples(device_mac, timestamp DESC);

CREATE TABLE IF NOT EXISTS health_scores (
    id BIGSERIAL PRIMARY KEY,
    device_mac VARCHAR(32) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    score INTEGER,
    risk_level VARCHAR(24) NOT NULL,
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_version VARCHAR(64) NOT NULL,
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_scores_device_time ON health_scores(device_mac, timestamp DESC);

CREATE TABLE IF NOT EXISTS alert_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_mac VARCHAR(32) NOT NULL,
    alarm_type VARCHAR(32) NOT NULL,
    alarm_layer VARCHAR(24) NOT NULL,
    alarm_level INTEGER NOT NULL,
    message TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    anomaly_probability NUMERIC(8,4),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_events_device_time ON alert_events(device_mac, created_at DESC);

CREATE TABLE IF NOT EXISTS device_status_history (
    id BIGSERIAL PRIMARY KEY,
    device_mac VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL,
    bind_status VARCHAR(24) NOT NULL DEFAULT '',
    source VARCHAR(32) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_status_history_device_time ON device_status_history(device_mac, changed_at DESC);

CREATE TABLE IF NOT EXISTS sensor_hourly_rollups (
    device_mac VARCHAR(32) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_end TIMESTAMPTZ NOT NULL,
    avg_heart_rate NUMERIC(8,2),
    avg_temperature NUMERIC(6,2),
    avg_blood_oxygen NUMERIC(8,2),
    avg_health_score NUMERIC(8,2),
    avg_battery NUMERIC(8,2),
    avg_steps NUMERIC(12,2),
    sos_count INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    risk_level VARCHAR(24),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (device_mac, bucket_start)
);

CREATE TABLE IF NOT EXISTS sensor_daily_rollups (
    device_mac VARCHAR(32) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_end TIMESTAMPTZ NOT NULL,
    avg_heart_rate NUMERIC(8,2),
    avg_temperature NUMERIC(6,2),
    avg_blood_oxygen NUMERIC(8,2),
    avg_health_score NUMERIC(8,2),
    avg_battery NUMERIC(8,2),
    avg_steps NUMERIC(12,2),
    sos_count INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    risk_level VARCHAR(24),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (device_mac, bucket_start)
);
