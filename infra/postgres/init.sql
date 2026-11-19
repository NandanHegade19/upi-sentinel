-- UPI Sentinel: starter schema (runs once, on first start of an empty database)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE customer (
    customer_id     UUID PRIMARY KEY,
    name_masked     TEXT NOT NULL,
    vpa_masked      TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    anonymised_at   TIMESTAMPTZ
);

CREATE TABLE transaction (
    txn_id          TEXT PRIMARY KEY,
    rail            TEXT NOT NULL CHECK (rail IN ('UPI','IMPS','NEFT','RTGS','MANDATE')),
    amount_inr      NUMERIC(14,2) NOT NULL CHECK (amount_inr > 0),
    payer_id        UUID NOT NULL REFERENCES customer(customer_id),
    payee_id        UUID NOT NULL REFERENCES customer(customer_id),
    current_status  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);

-- Append-only timeline; event_id makes replays idempotent (US-1.4)
CREATE TABLE txn_event (
    event_id        UUID PRIMARY KEY,
    txn_id          TEXT NOT NULL REFERENCES transaction(txn_id),
    status          TEXT NOT NULL,
    response_code   TEXT,
    source_system   TEXT NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    UNIQUE (txn_id, status) -- US-1.4: Strict idempotency constraint
);
CREATE INDEX idx_txn_event_txn_time ON txn_event (txn_id, event_time);