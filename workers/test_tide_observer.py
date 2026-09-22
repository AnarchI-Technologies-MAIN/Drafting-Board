import unittest
from unittest.mock import patch

import tide_observer
from tide_policy import HostSnapshot, TideSnapshot


GIB = 1024 ** 3


class TideObserverTests(unittest.TestCase):
    def test_host_snapshot_is_structurally_valid(self):
        snapshot = tide_observer.host_snapshot()

        self.assertGreaterEqual(snapshot.logical_cpus, 1)
        self.assertGreaterEqual(snapshot.load_1m, 0.0)
        self.assertGreater(snapshot.total_memory_bytes, 0)
        self.assertGreaterEqual(snapshot.available_memory_bytes, 0)
        self.assertGreaterEqual(snapshot.io_some_avg10, 0.0)

    def test_unreachable_database_returns_empty_snapshot(self):
        with patch.object(
            tide_observer,
            "postgres_reachable",
            return_value=False,
        ):
            snapshot, evidence = tide_observer.read_queue_snapshot()

        self.assertEqual(snapshot, TideSnapshot())
        self.assertFalse(evidence["database_reachable"])
        self.assertFalse(evidence["database_queried"])
        self.assertIsNotNone(evidence["database_error"])

    def test_shadow_observer_has_zero_execution_authority(self):
        host = HostSnapshot(
            logical_cpus=8,
            load_1m=1.0,
            total_memory_bytes=8 * GIB,
            available_memory_bytes=6 * GIB,
        )

        with patch.object(
            tide_observer,
            "host_snapshot",
            return_value=host,
        ), patch.object(
            tide_observer,
            "raw_swap_pages",
            return_value={
                "pswpin_pages": 0,
                "pswpout_pages": 0,
            },
        ), patch.object(
            tide_observer,
            "read_queue_snapshot",
            return_value=(
                TideSnapshot(),
                {
                    "database_reachable": False,
                    "database_queried": False,
                    "database_error": "test",
                    "counts": {},
                },
            ),
        ):
            result = tide_observer.observe()

        authority = result["authority"]

        self.assertFalse(authority["docker_start"])
        self.assertFalse(authority["container_start"])
        self.assertFalse(authority["worker_start"])
        self.assertFalse(authority["database_write"])
        self.assertFalse(authority["publication"])
        self.assertFalse(result["inventory_known"])
        self.assertEqual(
            result["decision"]["tide_state"],
            "UNKNOWN",
        )
        self.assertFalse(
            result["decision"]["admit_research"]
        )
        self.assertFalse(
            result["decision"]["admit_publisher"]
        )

    def test_psql_adapter_maps_realistic_counts(self):
        with patch.object(
            tide_observer,
            "postgres_reachable",
            return_value=True,
        ), patch.object(
            tide_observer,
            "_run_psql_scalar",
            side_effect=[
                [
                    "crawling|5",
                    "drained|8",
                    "enriched|2",
                    "held|2",
                    "queued|13",
                ],
                ["111"],
                [
                    "generating|1",
                    "quality_hold|6",
                    "staged|1",
                ],
            ],
        ):
            snapshot, evidence = tide_observer.read_queue_snapshot()

        self.assertTrue(evidence["database_reachable"])
        self.assertTrue(evidence["database_queried"])
        self.assertEqual(snapshot.queued, 13)
        self.assertEqual(snapshot.crawling, 5)
        self.assertEqual(snapshot.enriched, 2)
        self.assertEqual(snapshot.active_packets, 111)
        self.assertEqual(snapshot.generation_generating, 1)
        self.assertEqual(snapshot.quality_hold, 6)
        self.assertEqual(snapshot.staged, 1)

    def test_database_snapshot_mapping(self):
        counts = {
            "intake_queued": 2,
            "intake_crawling": 1,
            "intake_enriched": 3,
            "intake_monetizing": 4,
            "intake_ready": 5,
            "active_packets": 7,
            "generation_queued": 6,
            "generation_generating": 1,
            "generation_staged": 8,
            "generation_quality_hold": 9,
        }

        snapshot = TideSnapshot(
            queued=counts["intake_queued"],
            crawling=counts["intake_crawling"],
            enriched=counts["intake_enriched"],
            monetizing=counts["intake_monetizing"],
            ready=counts["intake_ready"],
            active_packets=counts["active_packets"],
            generation_queued=counts["generation_queued"],
            generation_generating=counts["generation_generating"],
            staged=counts["generation_staged"],
            quality_hold=counts["generation_quality_hold"],
        )

        self.assertEqual(snapshot.queued, 2)
        self.assertEqual(snapshot.active_packets, 7)
        self.assertEqual(snapshot.generation_queued, 6)
        self.assertEqual(snapshot.staged, 8)
        self.assertEqual(snapshot.quality_hold, 9)


if __name__ == "__main__":
    unittest.main()
