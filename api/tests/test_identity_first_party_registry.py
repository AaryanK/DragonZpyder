"""No auto-enabled first-party relying party can slip into reviewed migration."""
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "identity" /
       "schema_first_party_clients_staging.sql").read_text("utf-8")

def test_two_exact_hosts_and_both_clients_start_disabled():
    assert SQL.count(" 'openid operly:access', FALSE") == 2
    for uri in (
        "https://operly.dragonzpyder.xyz/api/auth/dragonzpyder/callback",
        "https://dragonzpyder.xyz/api/auth/dragonzpyder/web/callback",
    ):
        assert uri in SQL
    assert "ON CONFLICT (client_id) DO NOTHING" in SQL
    assert "RAISE EXCEPTION" in SQL
    assert "TRUE)" not in SQL
