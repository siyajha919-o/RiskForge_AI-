import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from .. import services as svc
from ..models import (
    GenerateReportRequest, ReportMeta, ReportResponse, ReportType, UserOut,
)
from ..security import current_user
from .. import report_render

# Binary formats are base64'd into the JSON envelope the client already handles.
BINARY_FORMATS = {
    "pdf": ("application/pdf", "pdf", report_render.to_pdf),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "xlsx", report_render.to_xlsx),
}

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

CATALOGUE = {
    ReportType.RISK_ASSESSMENT: ("Cyber Risk Assessment Report",
                                 "Quantified enterprise risk, drivers, and exposure by business unit"),
    ReportType.VULNERABILITY: ("Vulnerability Report",
                               "Open findings by severity, exploit status, and remediation backlog"),
    ReportType.COMPLIANCE: ("Compliance Report",
                            "Framework posture with evidence coverage and open gaps"),
    ReportType.INVESTMENT: ("Investment Optimization Report",
                            "Recommended control portfolio, ROSI, and diminishing-returns analysis"),
    ReportType.EXECUTIVE_SUMMARY: ("Executive Summary",
                                   "One-page board briefing of financial cyber exposure"),
}


def _inr(v) -> str:
    v = float(v or 0)
    if abs(v) >= 1e7:
        return f"Rs {v / 1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"Rs {v / 1e5:.2f} L"
    return f"Rs {v:,.0f}"


@router.get("", response_model=list[ReportMeta])
def catalogue(user: UserOut = Depends(current_user)):
    ready = svc.pipeline_has_run()
    generated = svc.graph_data().get("metadata", {}).get("generated_at")
    return [
        ReportMeta(id=rt, title=title, description=desc, available=ready, last_generated=generated)
        for rt, (title, desc) in CATALOGUE.items()
    ]


@router.post("/generate", response_model=ReportResponse)
def generate(payload: GenerateReportRequest, user: UserOut = Depends(current_user)):
    if not svc.pipeline_has_run():
        raise HTTPException(status_code=503,
                            detail="No computed results yet. Run the pipeline first.")

    graph = svc.graph_data()
    summary = svc.executive_summary()
    title = CATALOGUE[payload.report_type][0]
    now = datetime.now()
    score = svc.overall_risk_score()
    lines = [f"# {title}", "", f"Generated: {now.strftime('%d %b %Y, %H:%M')}", ""]

    if payload.report_type in (ReportType.EXECUTIVE_SUMMARY, ReportType.RISK_ASSESSMENT):
        lines += [
            "## Financial exposure", "",
            f"- Enterprise risk score: **{score}/100** ({svc.risk_level_from_score(score)})",
            f"- Expected annual loss: **{_inr(summary.get('total_expected_loss'))}**",
            f"- Value at Risk (95%): **{_inr(summary.get('var_95'))}**",
            f"- Value at Risk (99%): **{_inr(summary.get('var_99'))}**",
            f"- Critical vulnerabilities: **{svc.critical_vulnerability_count():,}**",
            f"- Active high-risk threat campaigns: **{svc.active_high_risk_threats():,}**",
            "",
        ]
        units = graph.get("business_unit_risk", {}).get("by_business_unit", [])
        if units:
            lines += ["## Exposure by business unit", "",
                      "| Business unit | Function | Assets | Expected annual loss |",
                      "|---|---|---|---|"]
            for u in units[:10]:
                lines.append(
                    f"| {u.get('business_unit_name') or u.get('business_unit_id')} "
                    f"| {u.get('business_function', '—')} | {u.get('asset_count', 0)} "
                    f"| {_inr(u.get('expected_annual_loss'))} |")
            lines.append("")

    if payload.report_type == ReportType.VULNERABILITY:
        dist = svc.severity_distribution()
        vulns = svc.vulnerabilities()
        kev = int(vulns["known_exploited"].sum()) if "known_exploited" in vulns else 0
        lines += [
            "## Vulnerability posture", "",
            f"- Total open findings: **{len(vulns):,}**",
            f"- Known exploited (CISA KEV): **{kev:,}**", "",
            "| Severity | Count |", "|---|---|",
            f"| Critical | {dist['critical']:,} |", f"| High | {dist['high']:,} |",
            f"| Medium | {dist['medium']:,} |", f"| Low | {dist['low']:,} |", "",
        ]

    if payload.report_type == ReportType.COMPLIANCE:
        report = svc.compliance_report()
        if report:
            lines += ["## Framework posture", "",
                      "| Framework | Requirements | Compliant | Evidence coverage |",
                      "|---|---|---|---|"]
            for name, fw in report.get("frameworks", {}).items():
                lines.append(f"| {name} | {fw.get('total_requirements', 0)} "
                             f"| {fw.get('compliance_pct', 0)}% | {fw.get('evidence_coverage_pct', 0)}% |")
            lines.append("")
        else:
            lines += ["_Compliance report not generated. Re-run the pipeline._", ""]

    if payload.report_type == ReportType.INVESTMENT:
        frontier = graph.get("efficient_frontier", [])
        lines += [
            "## Investment analysis", "",
            f"- Recommended investment: **{_inr(summary.get('total_investment'))}**",
            f"- Modelled risk reduction: **{summary.get('risk_reduction', 0)}%**",
            f"- Return on security investment: **{summary.get('rosi', 0)}x**", "",
        ]
        if frontier:
            lines += ["| Investment | Risk reduction | ROSI |", "|---|---|---|"]
            for p in frontier[:12]:
                lines.append(f"| {_inr(p.get('investment'))} | {p.get('risk_reduction', 0)}% "
                             f"| {p.get('rosi', 0)}x |")
            lines.append("")

    lines += ["---",
              "_Figures produced by FAIR Monte Carlo simulation over the current telemetry snapshot._"]

    markdown = "\n".join(lines)
    fmt = (payload.format or "markdown").lower()

    if fmt in BINARY_FORMATS:
        mime, extension, render = BINARY_FORMATS[fmt]
        try:
            blob = render(markdown, title)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
            raise HTTPException(
                status_code=500,
                detail=f"Could not render the {fmt.upper()} report: {exc}",
            ) from exc
        return ReportResponse(
            report_type=payload.report_type,
            format=fmt,
            generated_at=now.isoformat(),
            title=title,
            # Base64 so the binary survives the JSON envelope; the client decodes
            # it and hands the bytes to a Blob.
            content=base64.b64encode(blob).decode("ascii"),
            encoding="base64",
            mime_type=mime,
            file_extension=extension,
            data={"executive_summary": summary},
        )

    if fmt not in ("markdown", "md"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{payload.format}'. Use markdown, pdf or xlsx.",
        )

    return ReportResponse(
        report_type=payload.report_type,
        format="markdown",
        generated_at=now.isoformat(),
        title=title,
        content=markdown,
        encoding="text",
        mime_type="text/markdown",
        file_extension="md",
        data={"executive_summary": summary},
    )
