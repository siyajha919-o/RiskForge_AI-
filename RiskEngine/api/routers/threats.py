from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import services as svc
from ..models import (
    ThreatActor, UserOut, Vulnerability, VulnerabilityFilters, VulnerabilityPage,
)
from ..security import current_user

router = APIRouter(prefix="/api/v1/threats", tags=["threats"])


@router.get("/vulnerabilities", response_model=VulnerabilityPage)
def list_vulnerabilities(
    user: UserOut = Depends(current_user),
    severity: Optional[str] = None,
    risk_level: Optional[str] = None,
    known_exploited: Optional[bool] = None,
    vendor: Optional[str] = None,
    product: Optional[str] = None,
    min_cvss: Optional[float] = Query(None, ge=0, le=10),
    max_cvss: Optional[float] = Query(None, ge=0, le=10),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    asset_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "cvss_score",
    sort_desc: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    include_filters: bool = False,
):
    df = svc.vulnerabilities()
    if df.empty:
        return VulnerabilityPage(items=[], total=0, page=page, page_size=page_size,
                                 known_exploited_count=0)

    if severity:
        df = df[df["severity"].isin(severity.split(","))]
    if risk_level:
        df = df[df["risk_level"].isin(risk_level.split(","))]
    if known_exploited is not None:
        df = df[df["known_exploited"] == known_exploited]
    if product:
        df = df[df["product"].astype(str).str.contains(product, case=False, na=False)]
    if vendor and "vendor" in df.columns:
        df = df[df["vendor"].astype(str).str.contains(vendor, case=False, na=False)]
    if min_cvss is not None:
        df = df[df["cvss_score"] >= min_cvss]
    if max_cvss is not None:
        df = df[df["cvss_score"] <= max_cvss]
    if asset_id:
        df = df[df["asset_id"].astype(str) == asset_id]
    if date_from and "date_added" in df.columns:
        df = df[df["date_added"] >= date_from]
    if date_to and "date_added" in df.columns:
        df = df[df["date_added"] <= date_to]
    if search:
        needle = search.lower()
        haystack = (
            df.get("cve_id", "").astype(str).str.lower()
            + " " + df.get("description", "").astype(str).str.lower()
            + " " + df.get("vulnerability_id", "").astype(str).str.lower()
        )
        df = df[haystack.str.contains(needle, na=False)]

    total = len(df)
    kev_count = int(df["known_exploited"].sum()) if "known_exploited" in df else 0

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc)

    window = df.iloc[(page - 1) * page_size: page * page_size]

    items = [
        Vulnerability(
            vulnerability_id=str(r.get("vulnerability_id", "")),
            cve_id=(str(r["cve_id"]) if r.get("cve_id") == r.get("cve_id") and r.get("cve_id") else None),
            description=str(r.get("description", "")),
            cvss_score=float(r.get("cvss_score", 0) or 0),
            severity=r.get("severity", "Low"),
            known_exploited=bool(r.get("known_exploited", False)),
            exploit_available=bool(r.get("exploit_available", False)),
            vendor=r.get("vendor"),
            product=(str(r["product"]) if r.get("product") == r.get("product") and r.get("product") else None),
            date_added=r.get("date_added"),
            risk_level=r.get("risk_level", "Low"),
            asset_id=str(r.get("asset_id", "")) or None,
            attack_vector=r.get("attack_vector"),
            remediation_status=r.get("remediation_status"),
            patch_available=bool(r.get("patch_available", False)),
            risk_score=float(r.get("vulnerability_risk_score", 0) or 0),
        )
        for r in window.to_dict("records")
    ]

    filters = None
    if include_filters:
        full = svc.vulnerabilities()
        filters = VulnerabilityFilters(
            severities=sorted(full["severity"].dropna().unique().tolist()),
            vendors=[],
            products=sorted(full["product"].dropna().astype(str).unique().tolist())[:200],
            risk_levels=["Critical", "High", "Medium", "Low"],
            attack_vectors=sorted(full["attack_vector"].dropna().astype(str).unique().tolist())
            if "attack_vector" in full else [],
            cvss_range=[float(full["cvss_score"].min()), float(full["cvss_score"].max())],
            date_range=[
                str(full["date_added"].min()) if "date_added" in full else None,
                str(full["date_added"].max()) if "date_added" in full else None,
            ],
        )

    return VulnerabilityPage(items=items, total=total, page=page, page_size=page_size,
                             known_exploited_count=kev_count, filters=filters)


@router.get("/actors", response_model=list[ThreatActor])
def list_threats(
    user: UserOut = Depends(current_user),
    active_only: bool = False,
    limit: int = Query(100, ge=1, le=1000),
):
    df = svc.threats()
    if df.empty:
        return []
    if active_only and "campaign_active" in df.columns:
        df = df[df["campaign_active"]]
    if "exploit_probability" in df.columns:
        df = df.sort_values("exploit_probability", ascending=False)

    out = []
    for r in df.head(limit).to_dict("records"):
        out.append(ThreatActor(
            threat_id=str(r.get("threat_id", "")),
            threat_actor=str(r.get("threat_actor", "Unknown")),
            threat_category=str(r.get("threat_category", "Unknown")),
            attack_technique=(str(r["attack_technique"]) if r.get("attack_technique") else None),
            severity=r.get("severity", "Low"),
            exploit_probability=float(r.get("exploit_probability", 0) or 0),
            campaign_active=bool(r.get("campaign_active", False)),
            targeted_industry=r.get("targeted_industry"),
            associated_cve=(str(r["associated_cve"]) if r.get("associated_cve") else None),
            ransomware_indicator=bool(r.get("ransomware_indicator", False)),
            last_seen=str(r.get("last_seen")) if r.get("last_seen") else None,
        ))
    return out
