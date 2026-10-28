-- Owner-run migration. Back up/export the production branch first.
-- Apply only after pit_writer exists and has no UPDATE privilege on market_bars.
-- Existing rows deliberately remain NULL: their persistence time is unknown.
-- The insert trigger overrides supplied values so clients cannot backdate a row.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pit_writer') THEN
        RAISE EXCEPTION 'required role pit_writer must exist';
    END IF;
    IF has_table_privilege('pit_writer', 'public.market_bars', 'UPDATE') THEN
        RAISE EXCEPTION 'pit_writer must not have UPDATE on public.market_bars';
    END IF;
END
$$;

ALTER TABLE public.market_bars
    ADD COLUMN IF NOT EXISTS persisted_at timestamptz;

ALTER TABLE public.market_bars
    ALTER COLUMN persisted_at SET DEFAULT now();

CREATE OR REPLACE FUNCTION public.stamp_market_bars_persisted_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.persisted_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS market_bars_stamp_persisted_at ON public.market_bars;
CREATE TRIGGER market_bars_stamp_persisted_at
    BEFORE INSERT ON public.market_bars
    FOR EACH ROW
    EXECUTE FUNCTION public.stamp_market_bars_persisted_at();

COMMIT;
