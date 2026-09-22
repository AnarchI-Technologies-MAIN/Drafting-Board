import unittest
from datetime import datetime, timedelta, timezone

from work_ownership import (
    WORK_OWNERSHIP_VERSION,
    OwnershipState,
    WorkClaim,
    classify_ownership,
)


NOW = datetime(
    2026,
    8,
    26,
    9,
    0,
    tzinfo=timezone.utc,
)

STALE_AFTER = timedelta(minutes=60)

AVAILABLE = frozenset(
    {
        "queued",
    }
)

CLAIMED = frozenset(
    {
        "crawling",
        "generating",
        "reviewing",
        "illustrating",
    }
)


def decide(
    *,
    state,
    claimed_at=None,
    owner_present=None,
):
    return classify_ownership(
        WorkClaim(
            work_id="specimen-1",
            durable_state=state,
            claimed_at=claimed_at,
            owner_present=owner_present,
        ),
        available_states=AVAILABLE,
        claimed_states=CLAIMED,
        now=NOW,
        stale_after=STALE_AFTER,
    )


class WorkOwnershipTests(unittest.TestCase):
    def test_version_is_stable(self):
        self.assertEqual(
            WORK_OWNERSHIP_VERSION,
            "anarchi.work-ownership.v1",
        )

    def test_queued_unowned_work_is_available(self):
        result = decide(
            state="queued",
        )

        self.assertEqual(
            result.state,
            OwnershipState.AVAILABLE,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_live_recent_claim_is_owned(self):
        result = decide(
            state="crawling",
            claimed_at=NOW - timedelta(minutes=5),
            owner_present=True,
        )

        self.assertEqual(
            result.state,
            OwnershipState.OWNED,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_live_owner_blocks_age_only_recovery(self):
        result = decide(
            state="crawling",
            claimed_at=NOW - timedelta(hours=5),
            owner_present=True,
        )

        self.assertEqual(
            result.state,
            OwnershipState.STALE_BUT_OWNED,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_stale_claim_without_owner_is_orphaned(self):
        result = decide(
            state="crawling",
            claimed_at=NOW - timedelta(hours=5),
            owner_present=False,
        )

        self.assertEqual(
            result.state,
            OwnershipState.ORPHANED,
        )
        self.assertTrue(
            result.recoverable
        )

    def test_recent_claim_without_owner_does_not_recover(self):
        result = decide(
            state="generating",
            claimed_at=NOW - timedelta(minutes=5),
            owner_present=False,
        )

        self.assertEqual(
            result.state,
            OwnershipState.UNKNOWN,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_unknown_owner_fails_closed(self):
        result = decide(
            state="reviewing",
            claimed_at=NOW - timedelta(hours=5),
            owner_present=None,
        )

        self.assertEqual(
            result.state,
            OwnershipState.UNKNOWN,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_active_state_without_claim_timestamp_is_not_recoverable(self):
        result = decide(
            state="illustrating",
            claimed_at=None,
            owner_present=False,
        )

        self.assertEqual(
            result.state,
            OwnershipState.UNOWNED_ACTIVE,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_available_state_with_claim_timestamp_is_unknown(self):
        result = decide(
            state="queued",
            claimed_at=NOW - timedelta(hours=2),
            owner_present=False,
        )

        self.assertEqual(
            result.state,
            OwnershipState.UNKNOWN,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_unknown_durable_state_fails_closed(self):
        result = decide(
            state="mystery-state",
        )

        self.assertEqual(
            result.state,
            OwnershipState.UNKNOWN,
        )
        self.assertFalse(
            result.recoverable
        )

    def test_recovery_never_grants_admission(self):
        result = decide(
            state="crawling",
            claimed_at=NOW - timedelta(hours=5),
            owner_present=False,
        )

        self.assertTrue(
            result.recoverable
        )
        self.assertFalse(
            result.grants_admission
        )
        self.assertFalse(
            result.grants_execution
        )
        self.assertFalse(
            result.grants_publication
        )

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            classify_ownership(
                WorkClaim(
                    work_id="specimen",
                    durable_state="crawling",
                    claimed_at=datetime(
                        2026,
                        8,
                        26,
                        5,
                        0,
                    ),
                    owner_present=False,
                ),
                available_states=AVAILABLE,
                claimed_states=CLAIMED,
                now=NOW,
                stale_after=STALE_AFTER,
            )

    def test_nonpositive_stale_window_is_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            classify_ownership(
                WorkClaim(
                    work_id="specimen",
                    durable_state="crawling",
                    claimed_at=NOW,
                    owner_present=False,
                ),
                available_states=AVAILABLE,
                claimed_states=CLAIMED,
                now=NOW,
                stale_after=timedelta(0),
            )


if __name__ == "__main__":
    unittest.main()
