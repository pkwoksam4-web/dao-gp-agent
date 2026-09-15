from __future__ import annotations

import importlib
import unittest


def _subject():
    return importlib.import_module('baostock_turnover_full_v482')


class BaoStockTurnoverMaterializerV482Contracts(unittest.TestCase):
    def test_scope_validation_requires_exact_847_unique_exchange_qualified_symbols(self):
        m = _subject()
        symbols = [f'{i:06d}.SZ' for i in range(847)]
        self.assertEqual(m.validate_scope_symbols(symbols), symbols)

        with self.assertRaisesRegex(ValueError, '847'):
            m.validate_scope_symbols(symbols[:-1])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            m.validate_scope_symbols(symbols[:-1] + [symbols[0], symbols[0]])
        bad = list(symbols)
        bad[-1] = '846'
        with self.assertRaisesRegex(ValueError, 'exchange-qualified'):
            m.validate_scope_symbols(bad)

    def test_shard_gate_requires_every_selected_symbol_and_exact_row_count(self):
        m = _subject()
        self.assertTrue(m.shard_gate(
            symbols_selected=212,
            symbols_audited=212,
            expected_trade_rows=250_000,
            turnover_rows=250_000,
            review_n=0,
            error_n=0,
            unresolved_symbol_n=0,
        ))
        self.assertFalse(m.shard_gate(
            symbols_selected=212,
            symbols_audited=212,
            expected_trade_rows=250_000,
            turnover_rows=249_999,
            review_n=1,
            error_n=0,
            unresolved_symbol_n=0,
        ))
        self.assertFalse(m.shard_gate(
            symbols_selected=212,
            symbols_audited=211,
            expected_trade_rows=250_000,
            turnover_rows=250_000,
            review_n=0,
            error_n=1,
            unresolved_symbol_n=1,
        ))


if __name__ == '__main__':
    unittest.main()
