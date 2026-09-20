"""
Pydantic schemas — the contract between the RiskForge frontend and the engine.

Grouped by the screen that consumes them, so a frontend change has one obvious
place to look. Every monetary field is Indian Rupees; every *_pct field is
0-100, not 0-1.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ComplianceState(str, Enum):
    COMPLIANT = "Compliant"
    PARTIAL = "Partial"
    GAP = "Non-Compliant"


class Framework(str, Enum):
    NIST_CSF = "NIST CSF"
    ISO_27001 = "ISO 27001"
    CIS = "CIS Controls"
    RBI = "RBI CSF"
    SEBI = "SEBI CSCRF"


class Role(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    CISO = "CISO"
    ADMIN = "ADMIN"


class TrendPoint(BaseModel):
    date: str
    value: float


class Envelope(BaseModel):
    """Uniform wrapper so the frontend has one success/error shape to handle."""
    success: bool = True
    message: Optional[str] = None
    data: Any = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    remember_me: bool = False


class UserOut(BaseModel):
    email: EmailStr
    name: str
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

class RiskCards(BaseModel):
    overall_risk_score: float = Field(description="0-100, higher is worse")
    risk_level: RiskLevel
    expected_annual_loss: float
    total_financial_exposure: float = Field(description="Value at Risk, 95th percentile")
    critical_vulnerabilities: int
    active_high_risk_threats: int


class RiskDistribution(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class RiskContributor(BaseModel):
    name: str
    category: str
    expected_annual_loss: float
    contribution_pct: float
    risk_level: RiskLevel


class TopRisk(BaseModel):
    rank: int
    title: str
    asset_id: Optional[str] = None
    business_unit: Optional[str] = None
    expected_annual_loss: float
    risk_level: RiskLevel
    driver: str


class DashboardResponse(BaseModel):
    cards: RiskCards
    risk_trend: List[TrendPoint]
    financial_exposure_trend: List[TrendPoint]
    risk_distribution: RiskDistribution
    top_contributors: List[RiskContributor]
    top_risks: List[TopRisk]
    generated_at: Optional[str] = None
    run_mode: Optional[str] = None
    # False until two pipeline runs have been recorded, at which point the
    # trend is measured history rather than a back-cast. The UI labels it.
    trend_is_measured: bool = False


class RemediationAction(BaseModel):
    remediation_id: str
    action: str
    category: Optional[str] = None
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    business_service: Optional[str] = None
    vulnerability_id: Optional[str] = None
    required_control: Optional[str] = None
    estimated_cost: float = 0
    expected_loss_reduction: float = 0
    expected_risk_reduction_pct: float = 0
    return_per_rupee: float = 0
    implementation_days: int = 0
    priority: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[str] = None
    dependency: Optional[str] = None


class RemediationBacklog(BaseModel):
    total_actions: int = 0
    open_actions: int = 0
    overdue_actions: int = 0
    by_status: dict = {}
    by_priority: dict = {}
    by_category: List[dict] = []
    open_cost_to_clear: float = 0
    open_loss_reduction_available: float = 0


class RemediationResponse(BaseModel):
    recommendations: List[RemediationAction]
    backlog: RemediationBacklog


# ---------------------------------------------------------------------------
# Risk analysis
# ---------------------------------------------------------------------------

class RiskDriver(BaseModel):
    driver: str
    category: str = Field(description="vulnerability | threat | asset_criticality | control_weakness")
    contribution_pct: float
    expected_annual_loss: float
    detail: Optional[str] = None


class RiskAnalysisResponse(BaseModel):
    overall_risk_score: float
    risk_level: RiskLevel
    # The identity the screen is built around:
    #   incident_probability x financial_impact = cyber_risk (= expected annual loss)
    incident_probability: float = Field(description="0-1 annual probability of a material incident")
    estimated_financial_impact: float = Field(description="Loss magnitude if an incident occurs")
    expected_annual_loss: float = Field(description="probability x impact")
    risk_trend: List[TrendPoint]
    top_drivers: List[RiskDriver]
    contribution_breakdown: Dict[str, float] = Field(
        description="Share of total EAL by driver category, summing to 100"
    )


# ---------------------------------------------------------------------------
# Threats & vulnerabilities
# ---------------------------------------------------------------------------

class Vulnerability(BaseModel):
    vulnerability_id: str
    cve_id: Optional[str] = None
    description: str
    cvss_score: float
    severity: RiskLevel
    known_exploited: bool = Field(description="Present in the CISA KEV catalogue")
    exploit_available: bool = False
    vendor: Optional[str] = Field(default=None, description="Populated by NVD enrichment")
    product: Optional[str] = None
    date_added: Optional[str] = None
    risk_level: RiskLevel
    asset_id: Optional[str] = None
    attack_vector: Optional[str] = None
    remediation_status: Optional[str] = None
    patch_available: Optional[bool] = None
    risk_score: Optional[float] = None


class VulnerabilityFilters(BaseModel):
    """Distinct values for the filter row, so the UI never hardcodes options."""
    severities: List[str]
    vendors: List[str]
    products: List[str]
    risk_levels: List[str]
    attack_vectors: List[str]
    cvss_range: List[float]
    date_range: List[Optional[str]]


class VulnerabilityPage(BaseModel):
    items: List[Vulnerability]
    total: int
    page: int
    page_size: int
    known_exploited_count: int
    filters: Optional[VulnerabilityFilters] = None


class ThreatActor(BaseModel):
    threat_id: str
    threat_actor: str
    threat_category: str
    attack_technique: Optional[str] = Field(default=None, description="MITRE ATT&CK technique")
    severity: RiskLevel
    exploit_probability: float
    campaign_active: bool
    targeted_industry: Optional[str] = None
    associated_cve: Optional[str] = None
    ransomware_indicator: bool = False
    last_seen: Optional[str] = None


# ---------------------------------------------------------------------------
# Scenario simulation
# ---------------------------------------------------------------------------

class ControlOption(BaseModel):
    control_id: str
    name: str
    category: str
    annual_cost: float
    implementation_cost: float
    expected_risk_reduction_pct: float
    effectiveness_score: float
    description: Optional[str] = None


class SimulationRequest(BaseModel):
    control_ids: List[str] = Field(min_length=1, description="One or more controls applied together")
    budget_override: Optional[float] = None


class SimulationState(BaseModel):
    risk_score: float
    expected_annual_loss: float
    financial_exposure: float


class SimulationResponse(BaseModel):
    controls_applied: List[ControlOption]
    before: SimulationState
    after: SimulationState
    risk_reduction_pct: float
    financial_loss_avoided: float
    investment_cost: float
    rosi: float = Field(description="(loss avoided - cost) / cost")
    payback_months: Optional[float] = None


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

class ControlStatus(BaseModel):
    requirement_id: str
    framework: Framework
    function: Optional[str] = None
    category: Optional[str] = None
    control_id: str
    control_name: Optional[str] = None
    status: ComplianceState
    evidence_available: bool
    evidence_quality: str
    gap_score: Optional[float] = None
    associated_risk: Optional[float] = Field(default=None, description="EAL attributable to this gap")
    recommended_action: Optional[str] = None


class FrameworkSummary(BaseModel):
    framework: Framework
    total_requirements: int
    compliant: int
    partial: int
    gaps: int
    compliance_score: float
    evidence_coverage_pct: float


class ComplianceResponse(BaseModel):
    overall_compliance_score: float
    total_compliant: int
    total_partial: int
    total_gaps: int
    frameworks: List[FrameworkSummary]
    controls: List[ControlStatus]


# ---------------------------------------------------------------------------
# Investment optimization
# ---------------------------------------------------------------------------

class InvestmentRecommendation(BaseModel):
    control_id: str
    name: str
    category: Optional[str] = None
    investment_cost: float
    expected_risk_reduction_pct: float
    financial_loss_avoided: float
    rosi: float
    roi_pct: float
    priority: RiskLevel
    selected: bool = Field(description="Included in the optimal portfolio for this budget")


class FrontierPoint(BaseModel):
    investment: float
    risk_reduction_pct: float
    rosi: float
    is_optimal: bool = False


class OptimizationRequest(BaseModel):
    budget: float = Field(gt=0, description="Available annual security budget in INR")


class OptimizationResponse(BaseModel):
    budget: float
    total_allocated: float
    unallocated: float
    total_risk_reduction_pct: float
    total_loss_avoided: float
    portfolio_rosi: float
    recommendations: List[InvestmentRecommendation]
    frontier: List[FrontierPoint]


# ---------------------------------------------------------------------------
# Cyber risk network (3D graph)
# ---------------------------------------------------------------------------

class NetworkNode(BaseModel):
    id: str
    label: str
    type: str = Field(description="asset | vulnerability | business_unit")
    risk_level: RiskLevel
    expected_annual_loss: float = 0.0
    criticality: Optional[float] = None


class NetworkEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0
    kind: str = "exposes"


class NetworkResponse(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    attack_paths: List[Dict[str, Any]] = []
    stats: Dict[str, int] = {}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportType(str, Enum):
    RISK_ASSESSMENT = "risk_assessment"
    VULNERABILITY = "vulnerability"
    COMPLIANCE = "compliance"
    INVESTMENT = "investment"
    EXECUTIVE_SUMMARY = "executive_summary"


class ReportMeta(BaseModel):
    id: ReportType
    title: str
    description: str
    available: bool
    last_generated: Optional[str] = None
    formats: List[str] = ["json", "markdown"]


class GenerateReportRequest(BaseModel):
    report_type: ReportType
    format: Literal["markdown", "md", "pdf", "xlsx"] = "markdown"


class ReportResponse(BaseModel):
    report_type: ReportType
    format: str
    generated_at: str
    title: str
    # For markdown this is the document itself; for pdf/xlsx it is base64 bytes.
    # `encoding` tells the client which, so it never has to infer from `format`.
    content: str
    encoding: str = "text"
    mime_type: str = "text/markdown"
    file_extension: str = "md"
    data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Ask / pipeline
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(min_length=3)


class AskResponse(BaseModel):
    question: str
    answer: str
    mode: str
    model: Optional[str] = None
    context_used: List[str] = []


class PipelineStatus(BaseModel):
    running: bool
    last_run: Optional[Dict[str, Any]] = None
    inputs_changed_since_last_run: bool
    refresh_interval_seconds: int
