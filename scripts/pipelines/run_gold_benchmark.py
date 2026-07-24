"""Compare AXCalib evaluation reports with an approved semantic gold package."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib.calibration import (  # noqa: E402
    BenchmarkPrediction,
    GoldBenchmarkError,
    evaluate_gold_benchmark,
    load_gold_benchmark_package,
    prediction_from_report,
)
from axcalib.dossier import atomic_write_text  # noqa: E402
from axcalib.schemas import EvaluationReport  # noqa: E402

_MAX_REPORT_BYTES = 10_000_000
_MAX_REPORT_FILES = 10_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--reports",
        required=True,
        type=Path,
        help="Directory containing only the benchmark EvaluationReport JSON files.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--allow-offline-reference",
        action="store_true",
        help="Run a synthetic reference without producing an official pass/fail decision.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    package_path = args.package if args.package.is_absolute() else ROOT / args.package
    reports_path = args.reports if args.reports.is_absolute() else ROOT / args.reports
    try:
        package = load_gold_benchmark_package(
            package_path,
            allow_offline_reference=args.allow_offline_reference,
        )
        predictions = _load_predictions(reports_path)
        report = evaluate_gold_benchmark(
            package,
            predictions,
            allow_offline_reference=args.allow_offline_reference,
        )
    except (GoldBenchmarkError, OSError, ValueError) as error:
        print(f"gold benchmark failed: {error}", file=sys.stderr)
        return 2

    content = report.model_dump_json(indent=2) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_text(output, content)
    print(content, end="")
    if report.passed is False:
        return 1
    return 0


def _load_predictions(root: Path) -> tuple[BenchmarkPrediction, ...]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise GoldBenchmarkError("reports path must be a directory")
    paths = sorted(resolved.glob("*.json"))
    if not paths:
        raise GoldBenchmarkError("reports directory contains no JSON reports")
    if len(paths) > _MAX_REPORT_FILES:
        raise GoldBenchmarkError("reports directory exceeds the file-count limit")
    predictions = []
    for path in paths:
        if path.is_symlink():
            raise GoldBenchmarkError(f"report symlinks are not allowed: {path.name}")
        if path.stat().st_size > _MAX_REPORT_BYTES:
            raise GoldBenchmarkError(f"report exceeds size limit: {path.name}")
        try:
            report = EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise GoldBenchmarkError(f"invalid EvaluationReport JSON: {path.name}") from error
        predictions.append(prediction_from_report(report))
    return tuple(predictions)


if __name__ == "__main__":
    raise SystemExit(main())
