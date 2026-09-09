from __future__ import annotations

from typing import Any


PASS = 'FORMAL_ANCHOR_PIT_PASS'
BLOCKED = 'BLOCKED'


def formal_anchor_probe_gate(
    *,
    structural_blockers: list[str],
    binding_blockers: list[str],
    formal_anchor_change_date: str | None,
    formal_chain_mismatch_n: int,
    pit_verified: bool,
) -> str:
    if not isinstance(structural_blockers, list):
        raise ValueError('structural_blockers must be a list')
    if not isinstance(binding_blockers, list):
        raise ValueError('binding_blockers must be a list')
    if formal_anchor_change_date is not None and not isinstance(formal_anchor_change_date, str):
        raise ValueError('formal_anchor_change_date must be string or null')
    if not isinstance(formal_chain_mismatch_n, int) or isinstance(formal_chain_mismatch_n, bool):
        raise ValueError('formal_chain_mismatch_n must be an integer')
    if formal_chain_mismatch_n < 0:
        raise ValueError('formal_chain_mismatch_n must be nonnegative')
    if not isinstance(pit_verified, bool):
        raise ValueError('pit_verified must be boolean')

    if (
        not structural_blockers
        and not binding_blockers
        and bool(formal_anchor_change_date)
        and formal_chain_mismatch_n == 0
        and pit_verified
    ):
        return PASS
    return BLOCKED
