from __future__ import annotations

import effective_term_closure_v482 as base

# V4.82 stage-2 invariant overlay: the underlying full-path validation logic is
# unchanged; only the frozen evidence cardinalities advance from 58/28 to 66/34.
base.EXPECTED_EFFECTIVE_EVENT_N = 66
base.EXPECTED_CLOSED_SYMBOL_N = 34


if __name__ == '__main__':
    base.main()
