BEGIN READ ONLY;
SET LOCAL statement_timeout = '20s';

-- Database identity available without exposing the connection string.
SELECT current_database() AS database,
       current_user AS db_user,
       current_setting('server_version') AS server_version;

-- Frozen universe cardinalities.
SELECT watchlist_id, count(*)::bigint AS symbol_count
FROM public.watchlist_items
WHERE watchlist_id IN ('WAT-core10-final-v1', 'WAT-core13-observation-v1')
GROUP BY watchlist_id
ORDER BY watchlist_id;

-- Prospective Core13 ingest facts. trade_date and persisted counts are stored in report_json.
SELECT report_json::jsonb->>'trade_date' AS trade_date,
       count(*)::bigint AS completed_symbols,
       sum(((report_json::jsonb#>>'{persisted_verified,bars}')::int))::bigint AS persisted_bars,
       sum(((report_json::jsonb#>>'{persisted_verified,features}')::int))::bigint AS persisted_features,
       bool_and((report_json::jsonb->>'live_shadow_eligible')::boolean) AS all_live_shadow_eligible
FROM public.provider_sync_runs
WHERE status = 'COMPLETED'
  AND report_json::jsonb->>'mode' = 'LIVE_PIT_GITHUB_BRIDGE'
  AND report_json::jsonb->>'trade_date' IN ('2026-09-28', '2026-09-30')
GROUP BY report_json::jsonb->>'trade_date'
ORDER BY trade_date;

-- Feature rows are independently counted from the feature table.
SELECT snapshot_date, count(DISTINCT symbol)::bigint AS feature_symbols
FROM public.stock_feature_snapshots
WHERE snapshot_date IN ('2026-09-28', '2026-09-30')
GROUP BY snapshot_date
ORDER BY snapshot_date;

-- Ranking, Core13 observation and attestation linkage.
SELECT a.snapshot_date,
       a.id AS attestation_id,
       a.status AS attestation_status,
       a.evidence_json::jsonb->>'strategy_run_id' AS evidence_strategy_run_id,
       s.id AS strategy_run_id,
       a.evidence_json::jsonb->>'core13_observation_id' AS evidence_observation_id,
       o.id AS observation_id,
       a.evidence_hash
FROM public.live_shadow_run_attestations a
LEFT JOIN public.shadow_strategy_runs s
  ON s.id = a.evidence_json::jsonb->>'strategy_run_id'
LEFT JOIN public.shadow_observation_snapshots o
  ON o.id = a.evidence_json::jsonb->>'core13_observation_id'
WHERE a.snapshot_date IN ('2026-09-28', '2026-09-30')
ORDER BY a.snapshot_date;

-- Historical recovery must remain non-live and must not create features/forecast/shadow.
SELECT report_json::jsonb->>'trade_date' AS trade_date,
       count(*)::bigint AS recovered_symbols,
       bool_and(NOT (report_json::jsonb->>'live_shadow_eligible')::boolean) AS all_non_live,
       bool_and(NOT (report_json::jsonb->>'features_recovered')::boolean) AS no_features,
       bool_and(NOT (report_json::jsonb->>'forecast_or_shadow_generated')::boolean) AS no_forecast_or_shadow
FROM public.provider_sync_runs
WHERE report_json::jsonb->>'mode' = 'HISTORICAL_RECOVERY_NON_LIVE'
  AND report_json::jsonb->>'trade_date' = '2026-09-29'
GROUP BY report_json::jsonb->>'trade_date';

-- Protected probability and future-only settlement state.
SELECT (SELECT count(*)::bigint FROM public.forecast_runs) AS forecast_runs,
       (SELECT count(*)::bigint FROM public.forecast_items) AS forecast_items,
       (SELECT count(*)::bigint FROM public.shadow_strategy_runs) AS ranking_runs,
       (SELECT count(*)::bigint FROM public.shadow_observation_snapshots) AS observation_snapshots,
       (SELECT count(*)::bigint FROM public.live_shadow_run_attestations) AS attestations,
       (SELECT count(*)::bigint FROM public.shadow_maturity_snapshots) AS maturity_snapshots,
       (SELECT coalesce(sum(settled_count),0)::bigint FROM public.shadow_maturity_snapshots) AS settled_samples,
       (SELECT count(*)::bigint FROM public.settlement_integrity_snapshots) AS settlement_integrity_snapshots,
       (SELECT coalesce(sum(pending_count),0)::bigint FROM public.settlement_integrity_snapshots) AS pending_samples,
       (SELECT count(*)::bigint FROM public.shadow_cohort_snapshots) AS cohort_snapshots;

ROLLBACK;
