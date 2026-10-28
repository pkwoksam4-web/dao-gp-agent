-- Run manually by the database owner after creating pit_writer and pit_reader.
-- This migration is never applied by GitHub Actions.
-- Settlement attempts are append-only. The event_id primary key makes retries idempotent.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pit_writer') THEN
        RAISE EXCEPTION 'required role pit_writer must exist';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pit_reader') THEN
        RAISE EXCEPTION 'required role pit_reader must exist';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.agent_brain_settlement_events (
    event_id text PRIMARY KEY CHECK (event_id ~ '^[0-9a-f]{64}$'),
    strategy_run_id text NOT NULL,
    horizon_sessions smallint NOT NULL CHECK (horizon_sessions IN (5, 20)),
    settlement_trade_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('BLOCKED_DATA_GAP', 'SETTLED')),
    event_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (event_json ->> 'event_id' = event_id),
    CHECK (event_json ->> 'strategy_run_id' = strategy_run_id),
    CHECK ((event_json ->> 'horizon_sessions')::smallint = horizon_sessions),
    CHECK (event_json ->> 'settlement_trade_date' = settlement_trade_date::text),
    CHECK (event_json -> 'result' ->> 'status' = status)
);

CREATE INDEX IF NOT EXISTS agent_brain_settlement_events_run_horizon_idx
    ON public.agent_brain_settlement_events (strategy_run_id, horizon_sessions, created_at);

REVOKE ALL ON TABLE public.agent_brain_settlement_events FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE public.agent_brain_settlement_events FROM pit_writer;
GRANT SELECT, INSERT ON TABLE public.agent_brain_settlement_events TO pit_writer;
REVOKE ALL PRIVILEGES ON TABLE public.agent_brain_settlement_events FROM pit_reader;
GRANT SELECT ON TABLE public.agent_brain_settlement_events TO pit_reader;
