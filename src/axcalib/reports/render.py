"""Deterministic JSON and Markdown evaluation-report rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from axcalib.dossier.repository import atomic_write_text
from axcalib.schemas import EvaluationReport


@dataclass(frozen=True, slots=True)
class RenderedReport:
    """Paths and digest for one rendered report pair."""

    report_id: str
    json_path: Path
    markdown_path: Path
    json_sha256: str


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


class ReportRenderer:
    """Render typed evaluator output without changing its decision semantics."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def render(self, report: EvaluationReport) -> RenderedReport:
        """Persist canonical JSON and a reviewer-facing Markdown report."""

        directory = self.root / report.project_id / report.stage.value
        json_path = directory / f"{report.report_id}.json"
        markdown_path = directory / f"{report.report_id}.md"
        json_text = (
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        atomic_write_text(json_path, json_text)
        atomic_write_text(markdown_path, self._markdown(report))
        return RenderedReport(
            report_id=report.report_id,
            json_path=json_path,
            markdown_path=markdown_path,
            json_sha256=hashlib.sha256(json_text.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _markdown(report: EvaluationReport) -> str:
        lines = [
            f"# AXCalib {report.stage.value} 평가 초안",
            "",
            "> 이 문서는 Agent의 근거 기반 제안입니다. 관리자 HITL 결정이 아니며, "
            "단독으로 승인·인증 상태를 만들지 않습니다.",
            "",
            "## 실행 식별자",
            "",
            f"- Project: `{report.project_id}`",
            f"- Report: `{report.report_id}`",
            f"- Run: `{report.run_id}`",
            f"- Dossier revision: `{report.base_revision}`",
            f"- Snapshot: `{report.snapshot.snapshot_id}`",
            f"- Review profile: `{report.review_profile.selector}`",
            f"- Review profile SHA-256: `{report.review_profile.sha256}`",
            f"- Rubric: `{report.rubric_id}@{report.rubric_version}`",
            f"- Evaluator: `{report.evaluator_id}`",
            f"- Evidence SHA-256: `{report.evaluated_evidence_sha256}`",
            f"- Checklists: `{', '.join(report.checklist_refs) or 'none'}`",
            f"- References: `{', '.join(report.reference_ids) or 'none'}`",
            *(
                f"- Parser: `{run.parser_id}` status=`{run.status}` "
                f"pages=`{run.page_count}` text-pages=`{run.pages_with_text}`"
                for run in report.parser_runs
            ),
            "",
            "## Agent 제안",
            "",
            f"- Recommendation: **{report.recommendation.value}**",
            f"- Summary: {report.recommendation_summary}",
            "",
            "## 기준별 근거 점검",
            "",
            "| Criterion | Assessment | Observation | Evidence locator |",
            "|---|---|---|---|",
        ]
        for criterion in report.criteria:
            locators = (
                "<br>".join(
                    f"`{_cell(reference.locator)}` ({_cell(reference.source)})"
                    for reference in criterion.evidence_refs
                )
                or "없음"
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(f"{criterion.criterion_id} — {criterion.title}"),
                        criterion.assessment.value,
                        _cell(criterion.observation),
                        locators,
                    )
                )
                + " |"
            )
            if criterion.follow_up_questions:
                lines.extend(
                    [
                        "",
                        f"### {criterion.criterion_id} 보완 요청",
                        "",
                        *(f"- {question}" for question in criterion.follow_up_questions),
                    ]
                )
        lines.extend(
            [
                "",
                "## 유사과제 검색",
                "",
                f"- Status: `{report.retrieval.status}`",
                f"- Adapter: `{report.retrieval.adapter}`",
                f"- Similarity portion: `{report.retrieval.similarity_portion}`",
                f"- Corpus snapshot: `{report.retrieval.corpus_snapshot_id or 'none'}`",
                "",
                "## 한계",
                "",
                *(f"- {limitation}" for limitation in report.limitations),
                "",
                "## 관리자 HITL",
                "",
                "이 리포트에는 관리자 최종 결정이 포함되지 않습니다. 별도 승인 명령과 "
                "감사 이벤트가 필요합니다.",
                "",
            ]
        )
        return "\n".join(lines)


__all__ = ["RenderedReport", "ReportRenderer"]
