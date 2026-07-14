"""Run deterministic synthetic two-gate workflow scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axcalib import ActorRole, RecordingNotifier, TwoGateWorkflow, WorkflowRecord  # noqa: E402


def main() -> int:
    fixture_path = ROOT / "fixtures" / "synthetic" / "workflow_scenarios.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    failures = 0

    for scenario in fixture["scenarios"]:
        notifier = RecordingNotifier()
        workflow = TwoGateWorkflow(notifier)
        record = WorkflowRecord(project_id=scenario["project_id"])
        for event in scenario["events"]:
            role = ActorRole(event["actor"])
            if event["trigger"] == "assign_mentor":
                record = workflow.assign_mentor(record, event["mentor_ref"], actor_role=role)
            else:
                record = workflow.transition(record, event["trigger"], actor_role=role)
        passed = (
            record.status.value == scenario["expected_status"]
            and len(notifier.events) == scenario["expected_notifications"]
        )
        failures += int(not passed)
        results.append(
            {
                "scenario": scenario["id"],
                "status": record.status.value,
                "notification_count": len(notifier.events),
                "passed": passed,
            }
        )

    print(
        json.dumps(
            {
                "dataset": fixture["schema_version"],
                "synthetic": fixture["synthetic"],
                "scenario_count": len(results),
                "failures": failures,
                "results": results,
                "quality_claim": "workflow contract only; no model or retrieval quality claim",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

