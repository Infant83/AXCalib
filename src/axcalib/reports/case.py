"""Pure Markdown rendering for read-only case status and lifecycle summaries."""

from __future__ import annotations

import html
import re

from axcalib.schemas import CaseStatus, CaseSummary, GateReviewView

MARKDOWN_CONTROL = re.compile(r"([\\`*_\[\]()!])")


def _escaped(value: str) -> str:
    escaped = html.escape(value, quote=False)
    return MARKDOWN_CONTROL.sub(r"\\\1", escaped)


def _plain(value: str) -> str:
    return " ".join(_escaped(value).splitlines())


def _cell(value: str) -> str:
    escaped = _escaped(value).replace("\r\n", "\n").replace("\r", "\n")
    return escaped.replace("|", "\\|").replace("\n", "<br>")


def _code(value: str) -> str:
    cleaned = value.replace("`", "'")
    return f"`{_plain(cleaned)}`"


def _decision(value: GateReviewView) -> str:
    if value.human_decision is None:
        return "대기 또는 미결정"
    return value.human_decision.command


def _recommendation(value: GateReviewView) -> str:
    if value.agent_recommendation is None:
        return "평가초안 없음"
    return value.agent_recommendation.value


def _append_review(lines: list[str], value: GateReviewView) -> None:
    lines.extend(
        [
            f"### {value.stage.value}",
            "",
            f"- Agent 제안: **{_recommendation(value)}**",
            f"- 사람 결정: **{_decision(value)}**",
            f"- Report: {_code(value.report_id or 'none')}",
            f"- 평가 기준 revision: {_code(str(value.report_base_revision or 'none'))}",
            f"- 사람 보정 criterion: `{value.adjusted_criterion_count}`",
        ]
    )
    if value.agent_summary:
        lines.append(f"- Agent 요약: {_plain(value.agent_summary)}")
    if value.human_decision is not None:
        if value.human_decision.actor_id is not None:
            lines.append(f"- 결정자: {_code(value.human_decision.actor_id)}")
        if value.human_decision.rationale is not None:
            lines.append(f"- 결정 사유: {_plain(value.human_decision.rationale)}")
        if value.human_decision.authority_context is not None:
            lines.append(f"- 권한 근거: {_code(value.human_decision.authority_context)}")
    if value.criteria:
        lines.extend(
            [
                "",
                "| Criterion | Agent | 사람 반영 후 | 근거/관찰 |",
                "|---|---|---|---|",
            ]
        )
        for criterion in value.criteria:
            evidence = ", ".join(item.locator for item in criterion.evidence_refs) or "없음"
            observation = criterion.observation or ""
            detail = f"{observation}\nlocators: {evidence}"
            if criterion.adjustment_reason:
                detail += f"\n사람 보정: {criterion.adjustment_reason}"
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(f"{criterion.criterion_id} — {criterion.title}"),
                        criterion.agent_assessment.value,
                        criterion.effective_assessment.value,
                        _cell(detail),
                    )
                )
                + " |"
            )
    lines.append("")


class CaseViewRenderer:
    """Render current dossier projections without reading files or changing state."""

    @staticmethod
    def status_markdown(value: CaseStatus) -> str:
        """Render a compact, human-readable current status."""

        lines = [
            "# AXCalib 과제 현재 상태",
            "",
            "> Agent 평가와 권한 있는 사람의 결정은 별도 기록입니다. "
            "사람 결정이 없는 Agent 제안은 최종 승인이나 인증이 아닙니다.",
            "",
            f"- Project: {_code(value.project_id)}",
            f"- Display ID: {_code(value.display_id)}",
            f"- 제목: {_plain(value.title)}",
            f"- Dossier revision: `{value.revision}`",
            f"- 현재 상태: **{value.dossier_status.value}**",
            f"- Lifecycle stage: `{value.lifecycle_stage.value}`",
            f"- 종료 상태: `{'yes' if value.terminal else 'no'}`",
            f"- 대기 대상: `{value.waiting_for or 'none'}`",
            "",
            "## 다음 조치",
            "",
        ]
        if value.next_actions:
            lines.extend(
                f"- `{action.action_id}` — {action.description} "
                f"(required role: {_code(action.required_role)})"
                for action in value.next_actions
            )
        else:
            lines.append("- 현재 dossier 상태에서 제시할 다음 조치가 없습니다.")
        lines.append("")
        if value.latest_review is not None:
            lines.extend(["## 최신 평가와 사람 결정", ""])
            _append_review(lines, value.latest_review)
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def summary_markdown(value: CaseSummary) -> str:
        """Render both review gates and execution evidence as one lifecycle digest."""

        lines = [
            "# AXCalib 과제 요약",
            "",
            "> 이 요약은 최신 dossier와 불변 평가 report를 연결한 읽기 전용 projection입니다. "
            "Agent 원본 결과를 사람 보정으로 덮어쓰지 않습니다.",
            "",
            "## 과제",
            "",
            f"- Project: {_code(value.project_id)}",
            f"- Display ID: {_code(value.display_id)}",
            f"- 제목: {_plain(value.title)}",
            f"- Dossier revision: `{value.revision}`",
            f"- 현재 상태: **{value.dossier_status.value}**",
            f"- Review profile: `{value.review_profile or 'none'}`",
            f"- Artifact / notification / audit event: "
            f"`{value.artifact_count}` / `{value.notification_count}` / "
            f"`{value.audit_event_count}`",
            "",
            "## 두 Gate 한눈에 보기",
            "",
            "| Gate | Agent 제안 | 사람 결정 | 보정 criterion |",
            "|---|---|---|---:|",
            "| registration | "
            f"{_recommendation(value.registration)} | {_decision(value.registration)} | "
            f"{value.registration.adjusted_criterion_count} |",
            "| completion | "
            f"{_recommendation(value.completion)} | {_decision(value.completion)} | "
            f"{value.completion.adjusted_criterion_count} |",
            "",
            "## 등록심의",
            "",
        ]
        _append_review(lines, value.registration)
        lines.extend(
            [
                "## 수행 기록",
                "",
                f"- 시작: `{value.execution.started_at or 'none'}`",
                f"- 완료 제출: `{value.execution.completion_submitted_at or 'none'}`",
                f"- Mentor 배정: `{'yes' if value.execution.mentor_assigned else 'no'}`",
                f"- Progress note: `{value.execution.progress_note_count}`",
            ]
        )
        if value.execution.progress_notes:
            lines.extend(
                [
                    "",
                    "### Progress notes",
                    "",
                    *(f"- {_plain(note)}" for note in value.execution.progress_notes),
                ]
            )
        lines.extend(["", "## 완료평가", ""])
        _append_review(lines, value.completion)
        if value.artifacts:
            lines.extend(
                [
                    "## Artifact 무결성 참조",
                    "",
                    "| Artifact | Role | Media type | SHA-256 | Bytes |",
                    "|---|---|---|---|---:|",
                    *(
                        "| "
                        + " | ".join(
                            (
                                _cell(item.artifact_id),
                                _cell(item.role),
                                _cell(item.media_type),
                                item.sha256,
                                str(item.byte_size),
                            )
                        )
                        + " |"
                        for item in value.artifacts
                    ),
                    "",
                ]
            )
        if value.notifications:
            lines.extend(
                [
                    "## 관리자 승인요청 기록",
                    "",
                    "| Stage | Event | Required role | Delivery | Revision |",
                    "|---|---|---|---|---:|",
                    *(
                        "| "
                        + " | ".join(
                            (
                                item.stage.value,
                                _cell(item.event_type),
                                _cell(item.required_role),
                                _cell(item.delivery_status),
                                str(item.dossier_revision),
                            )
                        )
                        + " |"
                        for item in value.notifications
                    ),
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


__all__ = ["CaseViewRenderer"]
