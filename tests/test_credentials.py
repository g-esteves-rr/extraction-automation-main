import json
from pathlib import Path
from utils.credentials import (
    load_credentials,
    mark_expired,
    update_status,
    promote_valid_accounts,
    EXPIRED_PRIORITY,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _write_credentials(tmp_path: Path) -> Path:
    """
    Create a credentials.json file with the FULL expected schema.
    """
    data = {
        "accounts": [
            {
                "name": "X",
                "username": "X",
                "password": "X",
                "database": "DISCOPRD",
                "priority": 1,
                "status": "valid",
                "state": "valid",
                "last_used": "2026-01-28T09:55:32.602435Z",
                "status_changed_at": "2026-01-27T10:48:42.466343Z",
            },
            {
                "name": "Z",
                "username": "Z",
                "password": "Z",
                "database": "DISCOPRD",
                "priority": 2,
                "status": "failed",
                "state": "expired",
                "last_used": "2026-01-27T10:44:45.203015Z",
                "status_changed_at": "2026-01-27T10:44:45.203015Z",
            },
        ]
    }

    path = tmp_path / "credentials.json"
    path.write_text(json.dumps(data, indent=2))
    return path


# ------------------------------------------------------------------
# Tests: loading & ordering
# ------------------------------------------------------------------

def test_load_credentials_orders_by_priority(tmp_path):
    path = _write_credentials(tmp_path)

    accounts = load_credentials(path)

    assert accounts[0]["username"] == "X"
    assert accounts[1]["username"] == "Z"


# ------------------------------------------------------------------
# Tests: expiration handling
# ------------------------------------------------------------------

def test_mark_expired_updates_state_and_priority(tmp_path):
    path = _write_credentials(tmp_path)

    mark_expired(path, "X")
    accounts = load_credentials(path)

    x = next(a for a in accounts if a["username"] == "X")

    assert x["state"] == "expired"
    assert x["status"] == "expired"
    assert x["priority"] == EXPIRED_PRIORITY
    assert x["last_used"] is not None
    assert x["status_changed_at"] is not None


def test_mark_expired_does_not_remove_fields(tmp_path):
    path = _write_credentials(tmp_path)

    mark_expired(path, "X")
    accounts = load_credentials(path)
    x = next(a for a in accounts if a["username"] == "X")

    # Fields that MUST always exist
    required_fields = {
        "name",
        "username",
        "password",
        "database",
        "priority",
        "status",
        "state",
        "last_used",
        "status_changed_at",
    }

    assert required_fields.issubset(x.keys())


# ------------------------------------------------------------------
# Tests: status update
# ------------------------------------------------------------------

def test_update_status_only_changes_status_and_last_used(tmp_path):
    path = _write_credentials(tmp_path)

    update_status(path, "X", "failed")
    accounts = load_credentials(path)

    x = next(a for a in accounts if a["username"] == "X")

    assert x["status"] == "failed"
    assert x["state"] == "valid"          # untouched
    assert x["priority"] == 1              # untouched
    assert x["password"] == "X"            # untouched
    assert x["database"] == "DISCOPRD"
    assert x["last_used"] is not None


# ------------------------------------------------------------------
# Tests: priority rebalancing
# ------------------------------------------------------------------

def test_promote_valid_accounts_reorders_priorities(tmp_path):
    path = _write_credentials(tmp_path)

    promote_valid_accounts(path)
    accounts = load_credentials(path)

    valid = [a for a in accounts if a["state"] == "valid"]
    expired = [a for a in accounts if a["state"] == "expired"]

    assert valid[0]["priority"] == 1
    for acc in expired:
        assert acc["priority"] == EXPIRED_PRIORITY


# ------------------------------------------------------------------
# Tests: failure cases
# ------------------------------------------------------------------

def test_mark_expired_unknown_user_raises(tmp_path):
    path = _write_credentials(tmp_path)

    try:
        mark_expired(path, "UNKNOWN")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "User not found" in str(e)


def test_update_status_unknown_user_raises(tmp_path):
    path = _write_credentials(tmp_path)

    try:
        update_status(path, "UNKNOWN", "failed")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "User not found" in str(e)
