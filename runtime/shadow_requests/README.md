# Shadow request contract

Path: `runtime/shadow_requests/YYYY-MM-DD.json`, immutable after creation.

Schema:
```json
{
  "schema": "agent-brain-shadow-request/v1",
  "trade_date_cn": "YYYY-MM-DD",
  "requested_at": "real UTC timestamp after 17:30 Asia/Shanghai",
  "pit_manifest_path": "runtime/pit_manifests/YYYY-MM-DD.json",
  "modes": ["CORE10_RANKING_ONLY", "CORE13_OBSERVATION_ONLY"],
  "probability_forecast_allowed": false,
  "probability_blocker": "PROBABILITY_V1_6_EXECUTABLE_MISSING"
}
```

This request may produce only:
- `shadow_strategy_runs` for the frozen Core10 ranking candidate;
- `shadow_observation_snapshots` for Core13 observation.

It must never create probability forecast rows until probability-v1.6 executable semantics are independently recovered and accepted.
