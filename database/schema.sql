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
    user_id UUID REFERENCES users(id),
    status VARCHAR(24) NOT NULL DEFAULT 'online',
    bind_status VARCHAR(24) NOT NULL DEFAULT 'unbound',
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
