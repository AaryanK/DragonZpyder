"""Identity migration invariants; synthetic fixtures only."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.reconciliation import reconcile, IdentityMigrationConflict


def _users():
    return [{"id": "u-a", "email": "shared@example.test"}, {"id": "u-b", "email": "shared@example.test"}]


def test_verified_google_signin_and_discord_channel_link_have_distinct_authority():
    plan = reconcile(_users(),
                     [{"user_id": "u-a", "provider": "google", "provider_subject": "google-123"}],
                     [{"user_id": "u-a", "provider": "discord", "provider_subject": "discord-789", "verified_at": "2026-01-01"}])
    assert plan.links[0].login_eligible is True
    assert plan.links[1].login_eligible is False
    assert plan.user_ids == ("u-a", "u-b")


def test_email_is_not_used_to_merge_accounts():
    plan = reconcile(_users(), [], [])
    assert plan.user_ids == ("u-a", "u-b")


@pytest.mark.parametrize("users,auth,external", [
    (_users(), [
        {"user_id": "u-a", "provider": "google", "provider_subject": "same"},
        {"user_id": "u-b", "provider": "google", "provider_subject": "same"},
    ], []),
    (_users(), [{"user_id": "missing", "provider": "google", "provider_subject": "g"}], []),
    (_users(), [], [{"user_id": "u-a", "provider": "discord", "provider_subject": "d", "verified_at": None}]),
    ([{"id": "u-a"}, {"id": "u-a"}], [], []),
    (_users(), [{"user_id": "u-a", "provider": "google", "provider_subject": "g"}] * 2, []),
])
def test_conflicting_snapshots_fail_closed(users, auth, external):
    with pytest.raises(IdentityMigrationConflict):
        reconcile(users, auth, external)


def test_no_users_is_not_a_successful_migration():
    with pytest.raises(IdentityMigrationConflict):
        reconcile([], [], [])
