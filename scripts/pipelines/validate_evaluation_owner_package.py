"""Validate an Evaluation Owner rubric and semantic gold package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib.calibration import (  # noqa: E402
    GoldBenchmarkError,
    load_gold_benchmark_package,
)
from axcalib.policies import ReviewProfileRegistry, canonical_policy_sha256  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help="Validate a draft template without making it executable.",
    )
    parser.add_argument(
        "--allow-offline-reference",
        action="store_true",
        help="Validate an explicitly non-official synthetic reference package.",
    )
    parser.add_argument(
        "--print-hashes",
        action="store_true",
        help="Print canonical policy and raw file hashes needed by the manifest.",
    )
    parser.add_argument(
        "--hashes-only",
        action="store_true",
        help="Compute current standard-file hashes even before manifest hash fields are updated.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    package_path = args.package if args.package.is_absolute() else ROOT / args.package
    if args.hashes_only:
        try:
            print(
                json.dumps(
                    {"hashes": _compute_standard_hashes(package_path)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        except (OSError, ValueError) as error:
            print(f"evaluation owner package hash calculation failed: {error}", file=sys.stderr)
            return 2
        return 0
    try:
        package = load_gold_benchmark_package(
            package_path,
            allow_draft=args.allow_draft,
            allow_offline_reference=args.allow_offline_reference,
        )
    except GoldBenchmarkError as error:
        print(f"evaluation owner package validation failed: {error}", file=sys.stderr)
        return 2

    payload: dict[str, object] = {
        "valid": True,
        "selector": package.manifest.selector,
        "status": package.manifest.status.value,
        "official_quality_executable": package.manifest.status.value == "approved",
        "policy": f"{package.policy.policy_id}@{package.policy.version}",
        "label_count": len(package.labels),
        "registration_labels": sum(item.stage.value == "registration" for item in package.labels),
        "completion_labels": sum(item.stage.value == "completion" for item in package.labels),
        "thresholds_present": package.manifest.thresholds is not None,
    }
    if args.print_hashes:
        root = Path(package.package_root)
        payload["hashes"] = _compute_standard_hashes(root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compute_standard_hashes(package_path: Path) -> dict[str, str]:
    root = package_path.resolve()
    if not root.is_dir():
        raise ValueError("package must be a directory")
    files = {
        "manifest_sha256": root / "benchmark-manifest.yaml",
        "labels_sha256": root / "gold-labels.jsonl",
        "approval_sha256": root / "OWNER_APPROVAL.md",
    }
    for name, path in files.items():
        if not path.is_file():
            raise ValueError(f"missing standard package file for {name}")
        if path.stat().st_size > 20_000_000:
            raise ValueError(f"standard package file exceeds size limit for {name}")
    policy_path = root / "review-policy.yaml"
    if not policy_path.is_file() or policy_path.stat().st_size > 2_000_000:
        raise ValueError("review-policy.yaml is missing or exceeds the size limit")
    policy = ReviewProfileRegistry().load_file(policy_path).policy
    return {
        "manifest_sha256": _sha256(files["manifest_sha256"]),
        "policy_canonical_sha256": canonical_policy_sha256(policy),
        "labels_sha256": _sha256(files["labels_sha256"]),
        "approval_sha256": _sha256(files["approval_sha256"]),
    }


if __name__ == "__main__":
    raise SystemExit(main())
