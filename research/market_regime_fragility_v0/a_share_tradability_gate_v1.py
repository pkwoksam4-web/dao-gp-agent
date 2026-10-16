from __future__ import annotations

from datetime import datetime

VERSION = "A_SHARE_TRADABILITY_GATE_V1"

_VALID_LISTING = {"LISTED", "DELISTING", "DELISTED", "UNAVAILABLE"}
_VALID_ST = {"NORMAL", "ST", "STAR_ST", "UNAVAILABLE"}
_VALID_SUSPENSION = {"TRADING", "SUSPENDED", "UNAVAILABLE"}
_VALID_LIMIT = {
    "NONE",
    "UP_LOCKED_NO_BUY",
    "DOWN_LOCKED_NO_SELL",
    "LIMIT_TOUCH_EXECUTABLE",
    "UNAVAILABLE",
}
_VALID_LIQUIDITY = {"YES", "NO", "UNAVAILABLE"}


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _fail_closed(reasons: list[str]) -> dict:
    return {
        "version": VERSION,
        "buy_eligible": None,
        "sell_eligible": None,
        "rs_eligible": False,
        "reasons": reasons,
        "production_authorized": False,
    }


def evaluate_tradability(record: dict) -> dict:
    reasons: list[str] = []

    observed_at = _parse_aware(record.get("observed_at"))
    cutoff = _parse_aware(record.get("decision_cutoff"))
    if observed_at is None or cutoff is None:
        reasons.append("INVALID_TIMESTAMP")
    elif observed_at > cutoff:
        reasons.append("POST_CUTOFF_EVIDENCE")

    if record.get("pit_valid") is not True:
        reasons.append("PIT_INVALID")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or not provenance or any(not str(v).strip() for v in provenance.values()):
        reasons.append("PROVENANCE_MISSING")

    listing = record.get("listing_status")
    st_status = record.get("st_status")
    suspension = record.get("suspension_status")
    limit_state = record.get("limit_state")
    buy_liq = record.get("buy_liquidity_observed")
    sell_liq = record.get("sell_liquidity_observed")

    if listing not in _VALID_LISTING:
        reasons.append("LISTING_STATUS_INVALID")
    if st_status not in _VALID_ST:
        reasons.append("ST_STATUS_INVALID")
    if suspension not in _VALID_SUSPENSION:
        reasons.append("SUSPENSION_STATUS_INVALID")
    if limit_state not in _VALID_LIMIT:
        reasons.append("LIMIT_STATE_INVALID")
    if buy_liq not in _VALID_LIQUIDITY or sell_liq not in _VALID_LIQUIDITY:
        reasons.append("LIQUIDITY_EVIDENCE_INVALID")

    if not record.get("board") or record.get("board") == "UNAVAILABLE":
        reasons.append("BOARD_UNAVAILABLE")
    if not record.get("price_limit_rule_id") or record.get("price_limit_rule_id") == "UNAVAILABLE":
        reasons.append("PRICE_LIMIT_RULE_MISSING")

    sell_qty = record.get("sell_eligible_quantity")
    if not isinstance(sell_qty, (int, float)) or isinstance(sell_qty, bool) or sell_qty < 0:
        reasons.append("SELL_ELIGIBLE_QUANTITY_UNAVAILABLE")

    if listing == "UNAVAILABLE" or st_status == "UNAVAILABLE" or suspension == "UNAVAILABLE" or limit_state == "UNAVAILABLE":
        reasons.append("CRITICAL_STATE_UNAVAILABLE")
    if buy_liq == "UNAVAILABLE" or sell_liq == "UNAVAILABLE":
        reasons.append("LIQUIDITY_EVIDENCE_UNAVAILABLE")

    fatal_prefixes = {
        "INVALID_TIMESTAMP",
        "POST_CUTOFF_EVIDENCE",
        "PIT_INVALID",
        "PROVENANCE_MISSING",
        "LISTING_STATUS_INVALID",
        "ST_STATUS_INVALID",
        "SUSPENSION_STATUS_INVALID",
        "LIMIT_STATE_INVALID",
        "LIQUIDITY_EVIDENCE_INVALID",
        "BOARD_UNAVAILABLE",
        "PRICE_LIMIT_RULE_MISSING",
        "SELL_ELIGIBLE_QUANTITY_UNAVAILABLE",
        "CRITICAL_STATE_UNAVAILABLE",
        "LIQUIDITY_EVIDENCE_UNAVAILABLE",
    }
    if any(reason in fatal_prefixes for reason in reasons):
        return _fail_closed(reasons)

    if listing != "LISTED":
        return {
            "version": VERSION,
            "buy_eligible": False,
            "sell_eligible": False,
            "rs_eligible": False,
            "reasons": ["NOT_ACTIVE_LISTING"],
            "production_authorized": False,
        }

    if suspension == "SUSPENDED":
        return {
            "version": VERSION,
            "buy_eligible": False,
            "sell_eligible": False,
            "rs_eligible": False,
            "reasons": ["SUSPENDED"],
            "production_authorized": False,
        }

    buy_eligible = buy_liq == "YES"
    market_sellable = sell_liq == "YES"
    sell_eligible = market_sellable and sell_qty > 0

    decision_reasons: list[str] = []
    if limit_state == "UP_LOCKED_NO_BUY":
        buy_eligible = False
        decision_reasons.append("BUY_BLOCKED_PRICE_LIMIT")
    elif limit_state == "DOWN_LOCKED_NO_SELL":
        market_sellable = False
        sell_eligible = False
        decision_reasons.append("SELL_BLOCKED_PRICE_LIMIT")

    if buy_liq == "NO" and "BUY_BLOCKED_PRICE_LIMIT" not in decision_reasons:
        buy_eligible = False
        decision_reasons.append("BUY_LIQUIDITY_NOT_OBSERVED")
    if sell_liq == "NO" and "SELL_BLOCKED_PRICE_LIMIT" not in decision_reasons:
        market_sellable = False
        sell_eligible = False
        decision_reasons.append("SELL_LIQUIDITY_NOT_OBSERVED")
    if sell_qty == 0:
        sell_eligible = False
        decision_reasons.append("SELL_BLOCKED_T1")

    trade_evidence = record.get("executed_trade_evidence")
    if not isinstance(trade_evidence, bool):
        return _fail_closed(["EXECUTED_TRADE_EVIDENCE_INVALID"])
    if not trade_evidence:
        decision_reasons.append("NO_EXECUTED_TRADE_EVIDENCE")

    # RS eligibility describes whether the market itself is genuinely trading on both
    # sides. Position-specific T+1 sell eligibility is a separate execution constraint.
    rs_eligible = bool(
        buy_eligible
        and market_sellable
        and trade_evidence
        and limit_state in {"NONE", "LIMIT_TOUCH_EXECUTABLE"}
    )

    return {
        "version": VERSION,
        "buy_eligible": bool(buy_eligible),
        "sell_eligible": bool(sell_eligible),
        "rs_eligible": rs_eligible,
        "reasons": decision_reasons,
        "production_authorized": False,
    }
