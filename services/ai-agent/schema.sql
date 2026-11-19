CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- Clear the generic tables we created earlier
DROP TABLE IF EXISTS knowledge_chunk, transaction, txn_event, approval_request, audit_log, customer, fraud_flag CASCADE;

-- Tables from Screenshot 1
CREATE TABLE knowledge_chunk (
    chunk_id uuid PRIMARY KEY,
    document_name text,
    section text,
    page_number int4,
    published_date date,
    source_url text,
    text text,
    content_hash text,
    embedding vector(384)
);

CREATE TABLE transaction (
    txn_id text PRIMARY KEY,
    amount_inr numeric(14,2),
    created_at timestamptz,
    current_status text,
    payee_id uuid,
    payer_id uuid,
    rail text
);

CREATE TABLE txn_event (
    event_id uuid PRIMARY KEY,
    event_time timestamptz,
    response_code text,
    source_system text,
    status text,
    txn_id text
);

-- Tables from Screenshot 2
CREATE TABLE approval_request (
    request_id int4 PRIMARY KEY,
    action_type varchar(50),
    decided_at timestamp,
    decided_by varchar(50),
    decision_reason text,
    payload jsonb,
    run_id varchar(100),
    status varchar(20)
);

CREATE TABLE audit_log (
    log_id uuid PRIMARY KEY,
    action_type text,
    created_at timestamptz,
    details jsonb,
    txn_id text,
    user_role text
);

CREATE TABLE customer (
    customer_id uuid PRIMARY KEY,
    anonymised_at timestamptz,
    created_at timestamptz,
    name_masked text,
    vpa_masked text
);

CREATE TABLE fraud_flag (
    flag_id int4 PRIMARY KEY,
    analyst_feedback varchar(20),
    anomaly_score float8,
    created_at timestamp,
    fan_in_count int4,
    forwarding_ratio numeric(5,2),
    llm_explanation text,
    payee_id varchar(100),
    txn_id varchar(100)
);