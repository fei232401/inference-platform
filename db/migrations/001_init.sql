CREATE TABLE schema_migration (
    version    INTEGER     PRIMARY KEY,
    name       TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model (
    id                 BIGSERIAL   PRIMARY KEY,
    name               TEXT        NOT NULL,
    family             TEXT,
    parameter_billions NUMERIC(8,3),
    quantization       TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT model_name_unique UNIQUE (name)
);

CREATE TABLE backend (
    id              BIGSERIAL     PRIMARY KEY,
    name            TEXT          NOT NULL,
    url             TEXT          NOT NULL,
    engine          TEXT          NOT NULL,
    weight          NUMERIC(6,3)  NOT NULL DEFAULT 1.000,
    max_concurrency INTEGER       NOT NULL DEFAULT 1,
    cost_per_token  NUMERIC(12,8) NOT NULL DEFAULT 0,
    state           TEXT          NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT backend_name_unique          UNIQUE (name),
    CONSTRAINT backend_engine_valid         CHECK (engine IN ('ollama', 'openai')),
    CONSTRAINT backend_state_valid          CHECK (state IN ('active', 'draining', 'disabled')),
    CONSTRAINT backend_weight_positive      CHECK (weight > 0),
    CONSTRAINT backend_concurrency_positive CHECK (max_concurrency > 0),
    CONSTRAINT backend_cost_non_negative    CHECK (cost_per_token >= 0)
);

CREATE TABLE backend_model (
    backend_id BIGINT      NOT NULL REFERENCES backend(id) ON DELETE CASCADE,
    model_id   BIGINT      NOT NULL REFERENCES model(id)   ON DELETE CASCADE,
    loaded_at  TIMESTAMPTZ,
    PRIMARY KEY (backend_id, model_id)
);

CREATE TABLE backend_health_check (
    id         BIGSERIAL   PRIMARY KEY,
    backend_id BIGINT      NOT NULL REFERENCES backend(id) ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    healthy    BOOLEAN     NOT NULL,
    latency_ms INTEGER,
    error      TEXT,
    CONSTRAINT health_latency_non_negative CHECK (latency_ms IS NULL OR latency_ms >= 0)
);

CREATE TABLE api_key (
    id                    BIGSERIAL     PRIMARY KEY,
    key_prefix            TEXT          NOT NULL,
    key_hash              TEXT          NOT NULL,
    name                  TEXT          NOT NULL,
    scopes                TEXT[]        NOT NULL DEFAULT ARRAY['infer'],
    rate_limit_per_second NUMERIC(10,3),
    expires_at            TIMESTAMPTZ,
    revoked_at            TIMESTAMPTZ,
    last_used_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT api_key_hash_unique   UNIQUE (key_hash),
    CONSTRAINT api_key_rate_positive CHECK (rate_limit_per_second IS NULL OR rate_limit_per_second > 0)
);

CREATE TABLE request_log (
    request_id        UUID          PRIMARY KEY,
    api_key_id        BIGINT        REFERENCES api_key(id) ON DELETE SET NULL,
    session_id        TEXT,
    model_name        TEXT          NOT NULL,
    backend_id        BIGINT        REFERENCES backend(id) ON DELETE SET NULL,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    ttft_ms           NUMERIC(12,3),
    total_ms          NUMERIC(12,3),
    status            TEXT          NOT NULL,
    error_code        TEXT,
    started_at        TIMESTAMPTZ   NOT NULL,
    finished_at       TIMESTAMPTZ,
    CONSTRAINT request_status_valid  CHECK (status IN ('success', 'error', 'timeout', 'rejected')),
    CONSTRAINT request_tokens_non_negative CHECK (
        (prompt_tokens     IS NULL OR prompt_tokens     >= 0) AND
        (completion_tokens IS NULL OR completion_tokens >= 0)
    )
);

CREATE TABLE routing_decision (
    request_id      UUID        PRIMARY KEY REFERENCES request_log(request_id) ON DELETE CASCADE,
    policy          TEXT        NOT NULL,
    candidate_ids   BIGINT[]    NOT NULL,
    chosen_id       BIGINT      REFERENCES backend(id) ON DELETE SET NULL,
    score_snapshot  JSONB       NOT NULL,
    fallback_reason TEXT,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_backend_model_model     ON backend_model (model_id);

CREATE INDEX idx_health_backend_time     ON backend_health_check (backend_id, checked_at DESC);

CREATE INDEX idx_request_started         ON request_log (started_at DESC);
CREATE INDEX idx_request_backend_started ON request_log (backend_id, started_at DESC);
CREATE INDEX idx_request_session         ON request_log (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_request_failures        ON request_log (status, started_at DESC) WHERE status <> 'success';

CREATE INDEX idx_api_key_prefix          ON api_key (key_prefix);
CREATE INDEX idx_api_key_active          ON api_key (id) WHERE revoked_at IS NULL;

CREATE INDEX idx_routing_policy_time     ON routing_decision (policy, decided_at DESC);
CREATE INDEX idx_routing_chosen          ON routing_decision (chosen_id, decided_at DESC);
CREATE INDEX idx_routing_snapshot_gin    ON routing_decision USING GIN (score_snapshot);

INSERT INTO schema_migration (version, name) VALUES (1, 'init');
