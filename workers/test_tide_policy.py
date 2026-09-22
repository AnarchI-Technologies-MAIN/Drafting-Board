import unittest

from tide_policy import (
    HostPressure,
    HostSnapshot,
    TideSnapshot,
    TideState,
    decide,
)


GIB = 1024 ** 3


def healthy_host() -> HostSnapshot:
    return HostSnapshot(
        logical_cpus=8,
        load_1m=2.0,
        total_memory_bytes=8 * GIB,
        available_memory_bytes=6 * GIB,
        swap_in_bytes_per_sec=0,
        swap_out_bytes_per_sec=0,
        io_some_avg10=0,
    )


class TidePolicyTests(unittest.TestCase):
    def test_dry_healthy_host_admits_bounded_research(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(),
        )

        self.assertEqual(decision.host_pressure, HostPressure.HEALTHY)
        self.assertEqual(decision.tide_state, TideState.DRY)
        self.assertTrue(decision.admit_research)
        self.assertFalse(decision.admit_publisher)

    def test_low_existing_inventory_can_still_admit_research(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=1,
                drain_rate_per_minute=1.0,
            ),
        )

        self.assertEqual(decision.tide_state, TideState.LOW)
        self.assertTrue(decision.admit_research)
        self.assertTrue(decision.admit_crawler)

    def test_rising_backlog_closes_research(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=4,
                generation_queued=2,
                intake_rate_per_minute=5.0,
                drain_rate_per_minute=2.0,
            ),
        )

        self.assertEqual(decision.tide_state, TideState.RISING)
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertTrue(decision.admit_generator)

    def test_pressured_host_closes_research_and_generator(self):
        host = HostSnapshot(
            logical_cpus=8,
            load_1m=8.5,
            total_memory_bytes=8 * GIB,
            available_memory_bytes=4 * GIB,
        )

        decision = decide(
            host,
            TideSnapshot(
                queued=2,
                enriched=1,
                generation_queued=3,
            ),
        )

        self.assertEqual(decision.host_pressure, HostPressure.PRESSURED)
        self.assertEqual(decision.tide_state, TideState.PRESSURED)
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertTrue(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)

    def test_hot_memory_denies_everything(self):
        host = HostSnapshot(
            logical_cpus=8,
            load_1m=2.0,
            total_memory_bytes=8 * GIB,
            available_memory_bytes=512 * 1024 * 1024,
        )

        decision = decide(
            host,
            TideSnapshot(
                queued=10,
                enriched=10,
                ready=10,
                generation_queued=10,
            ),
        )

        self.assertEqual(decision.tide_state, TideState.HOT)
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_swap_activity_creates_pressure(self):
        host = HostSnapshot(
            logical_cpus=8,
            load_1m=2.0,
            total_memory_bytes=8 * GIB,
            available_memory_bytes=6 * GIB,
            swap_in_bytes_per_sec=4096,
        )

        decision = decide(host, TideSnapshot())

        self.assertEqual(decision.host_pressure, HostPressure.PRESSURED)
        self.assertFalse(decision.admit_research)

    def test_ready_work_admits_generator_when_healthy(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                ready=1,
                drain_rate_per_minute=1.0,
            ),
        )

        self.assertTrue(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_unknown_inventory_denies_everything(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(),
            inventory_known=False,
        )

        self.assertEqual(decision.tide_state, TideState.UNKNOWN)
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_generation_backlog_alone_closes_research(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                generation_queued=4,
            ),
        )

        self.assertEqual(decision.tide_state, TideState.BACKLOGGED)
        self.assertFalse(decision.admit_research)
        self.assertTrue(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_live_foundry_specimen_is_backlogged(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=13,
                crawling=5,
                enriched=2,
                monetizing=0,
                ready=0,
                active_packets=111,
                generation_queued=0,
                generation_generating=1,
                staged=1,
                quality_hold=6,
                intake_rate_per_minute=0.0,
                drain_rate_per_minute=0.0,
            ),
        )

        self.assertEqual(decision.tide_state, TideState.BACKLOGGED)
        self.assertFalse(decision.admit_research)
        self.assertTrue(decision.admit_crawler)
        self.assertTrue(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_generator_work_restrains_crawler(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=13,
                generation_queued=3,
            ),
        )

        self.assertTrue(decision.admit_generator)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_publisher)

    def test_crawler_resumes_when_generator_work_is_drained(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=13,
                generation_queued=0,
                ready=0,
            ),
        )

        self.assertFalse(decision.admit_generator)
        self.assertTrue(decision.admit_crawler)
        self.assertFalse(decision.admit_publisher)

    def test_pressured_host_denies_disk_heavy_crawler(self):
        host = HostSnapshot(
            logical_cpus=8,
            load_1m=1.0,
            total_memory_bytes=8_000_000_000,
            available_memory_bytes=1_500_000_000,
            swap_in_bytes_per_sec=0.0,
            swap_out_bytes_per_sec=0.0,
            io_some_avg10=0.0,
        )

        decision = decide(
            host,
            TideSnapshot(
                queued=20,
                enriched=2,
            ),
        )

        self.assertEqual(
            decision.host_pressure,
            HostPressure.PRESSURED,
        )
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertTrue(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)

    def test_disk_activity_without_pressure_does_not_block_crawler(self):
        host = healthy_host()

        decision = decide(
            host,
            TideSnapshot(
                queued=4,
                generation_queued=0,
                ready=0,
            ),
        )

        self.assertEqual(
            decision.host_pressure,
            HostPressure.HEALTHY,
        )
        self.assertTrue(decision.admit_crawler)

    def test_precision_compute_active_owns_floor(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=18,
                generation_queued=3,
            ),
            precision_compute_active=True,
        )

        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_live_crawler_finishes_before_generator_admission(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=18,
                generation_queued=3,
            ),
            crawler_active=True,
        )

        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_generator_gets_floor_after_live_owner_releases(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=18,
                generation_queued=3,
            ),
            precision_compute_active=False,
            crawler_active=False,
        )

        self.assertTrue(decision.admit_generator)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_publisher)

    def test_crawler_resumes_after_precision_queue_drains(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=18,
                generation_queued=0,
                ready=0,
            ),
            precision_compute_active=False,
            crawler_active=False,
        )

        self.assertFalse(decision.admit_generator)
        self.assertTrue(decision.admit_crawler)
        self.assertFalse(decision.admit_publisher)

    def test_unknown_workload_activity_fails_closed(self):
        decision = decide(
            healthy_host(),
            TideSnapshot(
                queued=18,
                generation_queued=3,
            ),
            workload_activity_known=False,
        )

        self.assertEqual(
            decision.tide_state,
            TideState.UNKNOWN,
        )
        self.assertFalse(decision.admit_research)
        self.assertFalse(decision.admit_crawler)
        self.assertFalse(decision.admit_outreach)
        self.assertFalse(decision.admit_generator)
        self.assertFalse(decision.admit_publisher)

    def test_tide_never_authorizes_publication(self):
        snapshots = (
            TideSnapshot(),
            TideSnapshot(queued=1),
            TideSnapshot(enriched=1),
            TideSnapshot(ready=1),
            TideSnapshot(generation_queued=1),
            TideSnapshot(staged=50),
            TideSnapshot(quality_hold=50),
        )

        for snapshot in snapshots:
            with self.subTest(snapshot=snapshot):
                self.assertFalse(
                    decide(healthy_host(), snapshot).admit_publisher
                )


if __name__ == "__main__":
    unittest.main()
