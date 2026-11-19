"""Check that the roadmap doesn't quietly claim unavailable tools are tested."""
from collections import Counter
from pathlib import Path
import re

CATALOG = Path(__file__).resolve().parents[1] / "agent_platform" / "benchmarks" / "WORKFLOW_CATALOG_100.md"


def test_workflow_inventory_has_100_unique_real_world_titles_and_honest_statuses():
    rows = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| WF-[0-9]{3} \|", line):
            columns = [cell.strip() for cell in line.split("|")[1:-1]]
            assert len(columns) == 4
            rows.append(columns)
    assert len(rows) == 100
    assert [r[0] for r in rows] == [f"WF-{i:03d}" for i in range(1, 101)]
    assert len({r[1] for r in rows}) == 100
    counts = Counter(r[3] for r in rows)
    assert counts == Counter({
        "implemented": 13, "operator_staging": 1,
        "integration": 44, "new_tool": 42
    })
    assert "not necessarily deployed" in CATALOG.read_text(encoding="utf-8")
