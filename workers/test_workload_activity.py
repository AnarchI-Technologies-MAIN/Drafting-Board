import unittest

from workload_activity import (
    WORKLOAD_ACTIVITY_VERSION,
    WorkloadFamily,
    classify_runtime,
    observation_from_inspect,
    snapshot_from_inspect,
)


def payload(
    *,
    service,
    role=None,
    ident="abc123",
    name="/specimen",
):
    env = []

    if role is not None:
        env.append(
            "ANARCHI_WORKLOAD_ROLE=" + role
        )

    return {
        "Id": ident,
        "Name": name,
        "Config": {
            "Labels": {
                "com.docker.compose.service": service,
            },
            "Env": env,
        },
    }


class WorkloadActivityTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            WORKLOAD_ACTIVITY_VERSION,
            "anarchi.workload-activity.v1",
        )

    def test_crawler_service_fallback(self):
        self.assertEqual(
            classify_runtime(
                compose_service="crawler-bot",
                explicit_role=None,
            ),
            WorkloadFamily.CRAWLER,
        )

    def test_llm_service_defaults_to_generator(self):
        self.assertEqual(
            classify_runtime(
                compose_service="llm-blogger",
                explicit_role=None,
            ),
            WorkloadFamily.GENERATOR,
        )

    def test_explicit_reviewer_overrides_llm_service(self):
        self.assertEqual(
            classify_runtime(
                compose_service="llm-blogger",
                explicit_role="atomic-reviewer",
            ),
            WorkloadFamily.REVIEWER,
        )

    def test_unknown_explicit_role_fails_closed(self):
        self.assertEqual(
            classify_runtime(
                compose_service="crawler-bot",
                explicit_role="mystery-role",
            ),
            WorkloadFamily.UNKNOWN,
        )

    def test_explicit_illustrator_role(self):
        self.assertEqual(
            classify_runtime(
                compose_service="some-service",
                explicit_role="illustrator",
            ),
            WorkloadFamily.ILLUSTRATOR,
        )

    def test_inspect_parser_reads_role(self):
        item = observation_from_inspect(
            payload(
                service="llm-blogger",
                role="atomic-reviewer",
            )
        )

        self.assertEqual(
            item.explicit_role,
            "atomic-reviewer",
        )
        self.assertEqual(
            item.workload_family,
            WorkloadFamily.REVIEWER,
        )

    def test_snapshot_detects_precision_compute(self):
        snapshot = snapshot_from_inspect(
            [
                payload(
                    service="crawler-bot",
                    ident="crawler",
                    name="/crawler",
                ),
                payload(
                    service="llm-blogger",
                    role="atomic-reviewer",
                    ident="reviewer",
                    name="/reviewer",
                ),
            ]
        )

        self.assertTrue(
            snapshot.crawler_active
        )
        self.assertTrue(
            snapshot.reviewer_active
        )
        self.assertTrue(
            snapshot.precision_compute_active
        )

    def test_crawler_alone_is_not_precision_compute(self):
        snapshot = snapshot_from_inspect(
            [
                payload(
                    service="crawler-bot",
                )
            ]
        )

        self.assertTrue(
            snapshot.crawler_active
        )
        self.assertFalse(
            snapshot.precision_compute_active
        )

    def test_empty_snapshot_has_no_activity(self):
        snapshot = snapshot_from_inspect(
            []
        )

        self.assertFalse(
            snapshot.crawler_active
        )
        self.assertFalse(
            snapshot.generator_active
        )
        self.assertFalse(
            snapshot.reviewer_active
        )
        self.assertFalse(
            snapshot.illustrator_active
        )
        self.assertFalse(
            snapshot.precision_compute_active
        )

    def test_activity_observer_has_zero_authority(self):
        snapshot = snapshot_from_inspect(
            [
                payload(
                    service="llm-blogger",
                )
            ]
        )

        self.assertFalse(
            snapshot.grants_admission
        )
        self.assertFalse(
            snapshot.grants_execution
        )
        self.assertFalse(
            snapshot.grants_recovery
        )
        self.assertFalse(
            snapshot.grants_publication
        )


if __name__ == "__main__":
    unittest.main()
