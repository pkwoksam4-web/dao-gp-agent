#!/usr/bin/env python3
"""DAO2 Module A historical L2 exact-reconstruction harness V1.

This harness is deliberately fail-closed. It does NOT assert that L2-derived
moneyflow is Tushare-equivalent. Its output is only an overlap candidate until
100% field-level exact match is proven against Jessica pinned rows.

Supported strict path:
- Shenzhen original-order messages + trade stream with aggressor side.
- Classify each execution by the ORIGINAL active order notional.
- Aggregate executed amount into Tushare large / extra-large buckets.

Shanghai is rejected by default because vendor order messages can represent
remaining quantity rather than original order quantity. Experimental Shanghai
runs may be used for overlap research only and MUST NOT be admitted directly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

BUCKET_SMALL_MAX = 50_000.0
BUCKET_MEDIUM_MAX = 200_000.0
BUCKET_LARGE_MAX = 1_000_000.0
PRICE_SCALE = 10_000.0
OUTPUT_AMOUNT_SCALE = 10_000.0  # CNY -> 万元

REQUIRED_OUTPUT_FIELDS = (
    "buy_lg_amount",
    "buy_elg_amount",
    "sell_lg_amount",
    "sell_elg_amount",
)


class ReconstructionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanonicalOrder:
    symbol: str
    date: str
    order_id: int
    side: str
    price_cny: float
    volume_shares: float

    @property
    def original_notional_cny(self) -> float:
        return self.price_cny * self.volume_shares


@dataclass(frozen=True)
class CanonicalTrade:
    symbol: str
    date: str
    trade_id: int
    side: str
    price_cny: float
    volume_shares: float
    ask_order_id: int
    bid_order_id: int

    @property
    def executed_notional_cny(self) -> float:
        return self.price_cny * self.volume_shares


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _date_str(value: Any) -> str:
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if len(s) != 8 or not s.isdigit():
        raise ReconstructionError(f"invalid YYYYMMDD date: {value!r}")
    return s


def _id_int(value: Any, field: str) -> int:
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s or not s.lstrip("-").isdigit():
        raise ReconstructionError(f"invalid {field}: {value!r}")
    v = int(s)
    if v <= 0:
        raise ReconstructionError(f"non-positive {field}: {value!r}")
    return v


def _positive_float(value: Any, field: str) -> float:
    try:
        v = float(value)
    except Exception as exc:
        raise ReconstructionError(f"invalid {field}: {value!r}") from exc
    if not math.isfinite(v) or v <= 0:
        raise ReconstructionError(f"non-positive/non-finite {field}: {value!r}")
    return v


def _normalize_side(value: Any) -> str:
    s = str(value).strip().upper()
    mapping = {
        "B": "B", "BUY": "B", "1": "B",
        "S": "S", "SELL": "S", "2": "S",
    }
    if s not in mapping:
        raise ReconstructionError(f"unknown aggressor/order side: {value!r}")
    return mapping[s]


def _bucket(original_notional_cny: float) -> str:
    if original_notional_cny < BUCKET_SMALL_MAX:
        return "sm"
    if original_notional_cny < BUCKET_MEDIUM_MAX:
        return "md"
    if original_notional_cny < BUCKET_LARGE_MAX:
        return "lg"
    return "elg"


def _rows_from_path(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except Exception as exc:
            raise ReconstructionError("pyarrow is required for parquet input") from exc
        table = pq.read_table(path)
        return table.to_pylist()
    raise ReconstructionError(f"unsupported input extension: {path.suffix}")


def _first(row: Mapping[str, Any], names: Sequence[str], field: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    raise ReconstructionError(f"missing required {field}; accepted columns={list(names)}")


def _symbol(row: Mapping[str, Any]) -> str:
    return str(_first(row, ("wind_code", "万得代码", "ts_code"), "symbol")).strip()


def _parse_orders(
    rows: Iterable[Mapping[str, Any]],
    symbol: str,
    trade_date: str,
    provider: str,
) -> List[CanonicalOrder]:
    out: List[CanonicalOrder] = []
    for row in rows:
        if _symbol(row) != symbol:
            continue
        d = _date_str(_first(row, ("date", "自然日", "trade_date"), "date"))
        if d != trade_date:
            continue

        order_type = str(row.get("order_type", row.get("委托类型", ""))).strip().upper()
        order_code = str(_first(row, ("order_code", "委托代码"), "order side")).strip().upper()

        # Cancellations are not original orders.
        if order_code == "D" or order_type == "D":
            continue

        if provider == "venvoo" and symbol.endswith(".SZ") and order_type not in ("0", "2"):
            # Dataset card explicitly documents Shenzhen limit-order encodings 0 and 2.
            # Market/unknown orders cannot be assigned an original notional safely here.
            raise ReconstructionError(
                f"unsupported Shenzhen original order_type={order_type!r}; "
                "cannot classify original order notional without guessing"
            )

        oid = _id_int(_first(row, ("order_id", "委托编号"), "order_id"), "order_id")
        side = _normalize_side(order_code)
        raw_price = _positive_float(_first(row, ("price", "委托价格"), "order price"), "order price")
        volume = _positive_float(_first(row, ("volume", "委托数量"), "order volume"), "order volume")
        price_cny = raw_price / PRICE_SCALE
        out.append(CanonicalOrder(symbol, d, oid, side, price_cny, volume))
    return out


def _parse_trades(
    rows: Iterable[Mapping[str, Any]],
    symbol: str,
    trade_date: str,
    provider: str,
) -> List[CanonicalTrade]:
    out: List[CanonicalTrade] = []
    for row in rows:
        if _symbol(row) != symbol:
            continue
        d = _date_str(_first(row, ("date", "自然日", "trade_date"), "date"))
        if d != trade_date:
            continue

        trade_code = str(row.get("trade_code", row.get("成交代码", ""))).strip().upper()
        if trade_code == "C":
            continue
        if provider == "alphat01" and trade_code != "F":
            raise ReconstructionError(f"unknown alphat01 trade_code={trade_code!r}")
        if provider == "venvoo" and trade_code and trade_code not in ("F",):
            raise ReconstructionError(f"unknown venvoo trade_code={trade_code!r}")

        tid = _id_int(_first(row, ("trade_id", "成交编号"), "trade_id"), "trade_id")
        side = _normalize_side(_first(row, ("bs_flag", "BS标志"), "aggressor side"))
        raw_price = _positive_float(_first(row, ("price", "成交价格"), "trade price"), "trade price")
        volume = _positive_float(_first(row, ("volume", "成交数量"), "trade volume"), "trade volume")
        ask_id = _id_int(_first(row, ("ask_order_id", "叫卖序号"), "ask_order_id"), "ask_order_id")
        bid_id = _id_int(_first(row, ("bid_order_id", "叫买序号"), "bid_order_id"), "bid_order_id")
        out.append(
            CanonicalTrade(
                symbol=symbol,
                date=d,
                trade_id=tid,
                side=side,
                price_cny=raw_price / PRICE_SCALE,
                volume_shares=volume,
                ask_order_id=ask_id,
                bid_order_id=bid_id,
            )
        )
    return out


def reconstruct(
    orders: Sequence[CanonicalOrder],
    trades: Sequence[CanonicalTrade],
    symbol: str,
    trade_date: str,
    *,
    allow_shanghai_experimental: bool = False,
) -> Dict[str, Any]:
    if symbol.endswith(".SH") and not allow_shanghai_experimental:
        raise ReconstructionError(
            "Shanghai reconstruction is disabled in strict mode because original-order "
            "notional semantics are not proven for this carrier"
        )

    index: Dict[int, CanonicalOrder] = {}
    for order in orders:
        if order.order_id in index:
            prev = index[order.order_id]
            if prev != order:
                raise ReconstructionError(f"ambiguous duplicate order_id={order.order_id}")
            continue
        index[order.order_id] = order

    if not index:
        raise ReconstructionError("no matching original orders")
    if not trades:
        raise ReconstructionError("no matching execution trades")

    agg = {
        "buy_sm_amount": 0.0,
        "buy_md_amount": 0.0,
        "buy_lg_amount": 0.0,
        "buy_elg_amount": 0.0,
        "sell_sm_amount": 0.0,
        "sell_md_amount": 0.0,
        "sell_lg_amount": 0.0,
        "sell_elg_amount": 0.0,
    }
    matched_trade_count = 0
    active_order_ids = set()

    for trade in trades:
        active_id = trade.bid_order_id if trade.side == "B" else trade.ask_order_id
        if active_id not in index:
            raise ReconstructionError(
                f"active order id {active_id} for trade {trade.trade_id} missing from order stream"
            )
        order = index[active_id]
        if order.side != trade.side:
            raise ReconstructionError(
                f"side mismatch trade={trade.trade_id} aggressor={trade.side} "
                f"active_order={active_id} side={order.side}"
            )

        bucket = _bucket(order.original_notional_cny)
        key = ("buy_" if trade.side == "B" else "sell_") + bucket + "_amount"
        agg[key] += trade.executed_notional_cny / OUTPUT_AMOUNT_SCALE
        matched_trade_count += 1
        active_order_ids.add(active_id)

    # Round only for stable serialization. Tushare identity comparison must still be exact
    # against source precision; caller should compare Decimal-normalized values.
    for key in agg:
        agg[key] = round(agg[key], 8)

    result = {
        "ts_code": symbol,
        "trade_date": trade_date,
        **agg,
        "matched_trade_count": matched_trade_count,
        "matched_active_order_count": len(active_order_ids),
        "strict_admission_allowed": False,
        "identity_status": "PENDING_JESSICA_EXACT_OVERLAP",
    }
    result["net_mf_amount"] = round(
        agg["buy_sm_amount"] + agg["buy_md_amount"] + agg["buy_lg_amount"] + agg["buy_elg_amount"]
        - agg["sell_sm_amount"] - agg["sell_md_amount"] - agg["sell_lg_amount"] - agg["sell_elg_amount"],
        8,
    )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", required=True, choices=("venvoo", "alphat01"))
    p.add_argument("--orders", required=True, type=Path)
    p.add_argument("--trades", required=True, type=Path)
    p.add_argument("--symbol", required=True)
    p.add_argument("--trade-date", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--allow-shanghai-experimental", action="store_true")
    args = p.parse_args()

    trade_date = _date_str(args.trade_date)
    if not (args.symbol.endswith(".SZ") or args.symbol.endswith(".SH")):
        raise ReconstructionError("symbol must end in .SZ or .SH")

    orders_raw = _rows_from_path(args.orders)
    trades_raw = _rows_from_path(args.trades)
    orders = _parse_orders(orders_raw, args.symbol, trade_date, args.provider)
    trades = _parse_trades(trades_raw, args.symbol, trade_date, args.provider)
    result = reconstruct(
        orders,
        trades,
        args.symbol,
        trade_date,
        allow_shanghai_experimental=args.allow_shanghai_experimental,
    )

    result["provenance"] = {
        "provider": args.provider,
        "orders_path": str(args.orders),
        "orders_sha256": _sha256(args.orders),
        "trades_path": str(args.trades),
        "trades_sha256": _sha256(args.trades),
        "source_unit_output_amounts": "10k CNY",
        "price_scale": PRICE_SCALE,
        "bucket_contract_cny": {
            "small": "<50000",
            "medium": ">=50000,<200000",
            "large": ">=200000,<1000000",
            "extra_large": ">=1000000",
        },
        "no_proxy": True,
        "no_imputation": True,
        "no_tolerance_identity_gate": True,
    }
    result["main_net_flow_cny"] = round(
        (
            result["buy_lg_amount"]
            + result["buy_elg_amount"]
            - result["sell_lg_amount"]
            - result["sell_elg_amount"]
        )
        * 10000,
        8,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["identity_status"],
        "strict_admission_allowed": result["strict_admission_allowed"],
        "symbol": args.symbol,
        "trade_date": trade_date,
        "matched_trade_count": result["matched_trade_count"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
