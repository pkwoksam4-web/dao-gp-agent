import unittest

from pit_st_collector_v480 import select_shard


class PitStShardV480Tests(unittest.TestCase):
    def test_four_shards_partition_scope_exactly_once(self):
        symbols = [f'{i:06d}.SZ' for i in range(17)]
        shards = [select_shard(symbols, i, 4) for i in range(4)]
        flattened = [s for shard in shards for s in shard]
        self.assertEqual(sorted(flattened), sorted(symbols))
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_shard_is_deterministic_by_position_modulus(self):
        symbols = ['A', 'B', 'C', 'D', 'E', 'F']
        self.assertEqual(select_shard(symbols, 0, 3), ['A', 'D'])
        self.assertEqual(select_shard(symbols, 1, 3), ['B', 'E'])
        self.assertEqual(select_shard(symbols, 2, 3), ['C', 'F'])

    def test_invalid_shard_arguments_fail(self):
        with self.assertRaises(ValueError):
            select_shard(['A'], 4, 4)
        with self.assertRaises(ValueError):
            select_shard(['A'], 0, 0)


if __name__ == '__main__':
    unittest.main()
