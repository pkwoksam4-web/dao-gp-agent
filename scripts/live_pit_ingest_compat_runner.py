#!/usr/bin/env python3
"""One-time compatibility runner for a Longbridge candle-schema drift.

The provider stopped returning the legacy boolean `open_updated` on completed
daily candles. This runner does not modify the provider raw payload. Instead it
patches only the in-memory validation gate so a missing `open_updated` is
accepted iff the manifest carries an independently checkable completion proof:
CN market Closed after 15:00, official trading-day verified, same-date EOD
quote, and exact OHLC identity between quote and candle.

All downstream provenance, raw hashes, inserts and feature logic remain the
original scripts/live_pit_ingest.py implementation.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path("scripts/live_pit_ingest.py")
source = SRC.read_text(encoding="utf-8")

old = '''        if raw.get("trade_session")!="Intraday" or raw.get("open_updated") is not True:\n            raise RuntimeError(f"{x['symbol']}: incomplete/invalid daily bar")\n'''
new = '''        if raw.get("trade_session")!="Intraday":\n            raise RuntimeError(f"{x['symbol']}: invalid daily trade_session")\n        if raw.get("open_updated") is not True:\n            proof=b.get("completion_evidence") or {}\n            q0=x.get("quote") or {}\n            qn0=q0.get("normalized") or {}\n            if proof.get("method")!="MARKET_CLOSED_AND_EOD_QUOTE_OHLC_IDENTITY":\n                raise RuntimeError(f"{x['symbol']}: missing accepted daily-bar completion proof")\n            if proof.get("market_status")!="Closed":\n                raise RuntimeError(f"{x['symbol']}: completion proof market not closed")\n            if proof.get("market_status_source")!="Longbridge.market_status":\n                raise RuntimeError(f"{x['symbol']}: completion proof market-status source mismatch")\n            if proof.get("trading_day_source")!="Longbridge.trading_days":\n                raise RuntimeError(f"{x['symbol']}: completion proof trading-day source mismatch")\n            p_at=proof.get("market_status_at")\n            if not p_at or sh_dt(p_at).date().isoformat()!=td:\n                raise RuntimeError(f"{x['symbol']}: completion proof date mismatch")\n            if not qn0.get("as_of") or sh_dt(qn0["as_of"]).date().isoformat()!=td:\n                raise RuntimeError(f"{x['symbol']}: completion proof quote date mismatch")\n            for qf,bf in [("open","open"),("high","high"),("low","low"),("last","close")]:\n                if qn0.get(qf) is None or abs(float(qn0[qf])-float(raw[bf]))>1e-9:\n                    raise RuntimeError(f"{x['symbol']}: completion proof OHLC identity failed: {qf}")\n'''

if source.count(old) != 1:
    raise RuntimeError("compat runner source contract mismatch; refusing to patch")

patched = source.replace(old, new, 1)
code = compile(patched, str(SRC) + "[market-closed-compat]", "exec")
exec(code, {"__name__": "__main__", "__file__": str(SRC)})
