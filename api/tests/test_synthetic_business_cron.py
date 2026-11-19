"""Synthetic five-minute canary must never receive Operly credentials."""
import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform import synthetic_business_cron as cron


def _enable(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
    monkeypatch.setenv("DRAGONZPYDER_SYNTHETIC_BUSINESS_CANARY_ENABLED", "1")
    for key in cron._ALLOWED_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_runner_disabled_by_default(monkeypatch, capsys):
    monkeypatch.delenv("DRAGONZPYDER_SYNTHETIC_BUSINESS_CANARY_ENABLED", raising=False)
    assert cron.execute() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "disabled"


def test_runner_refuses_leaked_service_tokens(monkeypatch, capsys):
    _enable(monkeypatch)
    monkeypatch.setenv("DRAGONZPYDER_OPERLY_CANARY_LEASE", "private-lease")
    assert cron.execute() == 3
    body = capsys.readouterr().out
    assert json.loads(body)["status"] == "unexpected_credentials"
    assert "private-lease" not in body


def test_runner_runs_exactly_one_fixed_offline_suite(monkeypatch, capsys):
    _enable(monkeypatch)
    seen = []

    def fake_run(args, **kwargs):
        seen.append((args, kwargs))
        return CompletedProcess(args=args, returncode=0, stdout="14 passed", stderr="")

    monkeypatch.setattr(cron.subprocess, "run", fake_run)
    assert cron.execute() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["paid_model_calls"] == 0
    assert result["external_mutations"] == 0
    assert result["execution"] == "synthetic_broker_contract_only"
    assert len(seen) == 1
    args, opts = seen[0]
    assert args[1:4] == ["-m", "pytest", "-q"]
    assert args[-1].endswith("test_operly_business_canary.py")
    assert opts["timeout"] == 90
    assert "OPENROUTER_API_KEY" not in opts["env"]
    assert opts["env"]["DRAGONZPYDER_STAGE"] == "staging"


def test_runner_surfaces_failure_without_sensitive_output(monkeypatch, capsys):
    _enable(monkeypatch)
    monkeypatch.setattr(
        cron.subprocess, "run",
        lambda args, **kwargs: CompletedProcess(args=args, returncode=1,
                                               stdout="private fixture", stderr="secret fixture"),
    )
    assert cron.execute() == 1
    text = capsys.readouterr().out
    assert json.loads(text)["status"] == "failed"
    assert "private fixture" not in text and "secret fixture" not in text


def test_runner_requires_staging_even_with_enabled_flag(monkeypatch, capsys):
    _enable(monkeypatch)
    monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
    assert cron.execute() == 2
    assert json.loads(capsys.readouterr().out)["status"] == "disabled"
