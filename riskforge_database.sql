-- RiskForge_AI PostgreSQL Database
-- Designed for: Risk Quantification, Scenario Simulation, Investment Optimization,
-- Compliance Mapping, Data Ingestion, Authentication and Audit Logging.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- 1. ORGANIZATIONS & USERS
-- =========================================================

CREATE TABLE organizations (
    organization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    industry VARCHAR(100),
    annual_revenue NUMERIC(18,2),
    risk_appetite VARCHAR(30) DEFAULT 'MEDIUM'
        CHECK (risk_appetite IN ('LOW','MEDIUM','HIGH')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'ANALYST'
        CHECK (role IN ('ADMIN','ANALYST','AUDITOR','VIEWER')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 2. ASSET INVENTORY
-- =========================================================

CREATE TABLE assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    asset_name VARCHAR(150) NOT NULL,
    asset_type VARCHAR(80) NOT NULL,
    owner_name VARCHAR(150),
    business_value NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (business_value >= 0),
    confidentiality_score SMALLINT DEFAULT 3 CHECK (confidentiality_score BETWEEN 1 AND 5),
    integrity_score SMALLINT DEFAULT 3 CHECK (integrity_score BETWEEN 1 AND 5),
    availability_score SMALLINT DEFAULT 3 CHECK (availability_score BETWEEN 1 AND 5),
    criticality VARCHAR(20) DEFAULT 'MEDIUM'
        CHECK (criticality IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_assets_org ON assets(organization_id);

-- =========================================================
-- 3. THREATS & VULNERABILITIES
-- =========================================================

CREATE TABLE threats (
    threat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    threat_name VARCHAR(150) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    default_probability NUMERIC(7,6)
        CHECK (default_probability IS NULL OR default_probability BETWEEN 0 AND 1)
);

CREATE TABLE vulnerabilities (
    vulnerability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    cve_id VARCHAR(40),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    cvss_score NUMERIC(4,1) CHECK (cvss_score IS NULL OR cvss_score BETWEEN 0 AND 10),
    severity VARCHAR(20)
        CHECK (severity IS NULL OR severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN','IN_PROGRESS','MITIGATED','ACCEPTED')),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_vulnerabilities_asset ON vulnerabilities(asset_id);
CREATE INDEX idx_vulnerabilities_status ON vulnerabilities(status);

-- =========================================================
-- 4. RISK QUANTIFICATION
-- =========================================================

CREATE TABLE risk_assessments (
    risk_assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    threat_id UUID REFERENCES threats(threat_id) ON DELETE SET NULL,
    assessment_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Quantification inputs
    annual_rate_of_occurrence NUMERIC(10,4) NOT NULL DEFAULT 0 CHECK (annual_rate_of_occurrence >= 0),
    loss_per_event NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (loss_per_event >= 0),

    -- Expected Annual Loss = ARO * Loss Per Event
    expected_annual_loss NUMERIC(18,2) GENERATED ALWAYS AS
        (annual_rate_of_occurrence * loss_per_event) STORED,

    value_at_risk NUMERIC(18,2),
    confidence_level NUMERIC(5,4)
        CHECK (confidence_level IS NULL OR confidence_level BETWEEN 0 AND 1),

    likelihood_score NUMERIC(5,2) CHECK (likelihood_score IS NULL OR likelihood_score BETWEEN 0 AND 10),
    impact_score NUMERIC(5,2) CHECK (impact_score IS NULL OR impact_score BETWEEN 0 AND 10),
    risk_score NUMERIC(7,2),

    risk_level VARCHAR(20)
        CHECK (risk_level IS NULL OR risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    notes TEXT
);

CREATE INDEX idx_risk_assessments_org ON risk_assessments(organization_id);
CREATE INDEX idx_risk_assessments_asset ON risk_assessments(asset_id);
CREATE INDEX idx_risk_assessments_date ON risk_assessments(assessment_date DESC);

CREATE TABLE risk_drivers (
    risk_driver_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_assessment_id UUID NOT NULL REFERENCES risk_assessments(risk_assessment_id) ON DELETE CASCADE,
    driver_name VARCHAR(150) NOT NULL,
    contribution_percent NUMERIC(5,2) NOT NULL
        CHECK (contribution_percent BETWEEN 0 AND 100),
    explanation TEXT
);

-- =========================================================
-- 5. SECURITY CONTROLS
-- =========================================================

CREATE TABLE security_controls (
    control_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    control_code VARCHAR(50) UNIQUE,
    control_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    implementation_cost NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (implementation_cost >= 0),
    annual_maintenance_cost NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (annual_maintenance_cost >= 0),
    effectiveness_percent NUMERIC(5,2) NOT NULL DEFAULT 0
        CHECK (effectiveness_percent BETWEEN 0 AND 100),
    implementation_status VARCHAR(25) NOT NULL DEFAULT 'PLANNED'
        CHECK (implementation_status IN ('PLANNED','IN_PROGRESS','IMPLEMENTED','RETIRED'))
);

CREATE TABLE asset_controls (
    asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
    effectiveness_override NUMERIC(5,2)
        CHECK (effectiveness_override IS NULL OR effectiveness_override BETWEEN 0 AND 100),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (asset_id, control_id)
);

-- =========================================================
-- 6. COMPLIANCE
-- =========================================================

CREATE TABLE compliance_frameworks (
    framework_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    framework_code VARCHAR(50) NOT NULL UNIQUE,
    framework_name VARCHAR(150) NOT NULL,
    version VARCHAR(50),
    description TEXT
);

CREATE TABLE compliance_requirements (
    requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    framework_id UUID NOT NULL REFERENCES compliance_frameworks(framework_id) ON DELETE CASCADE,
    requirement_code VARCHAR(100) NOT NULL,
    title VARCHAR(250) NOT NULL,
    description TEXT,
    UNIQUE (framework_id, requirement_code)
);

CREATE TABLE control_compliance_mappings (
    control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
    requirement_id UUID NOT NULL REFERENCES compliance_requirements(requirement_id) ON DELETE CASCADE,
    coverage_percent NUMERIC(5,2) NOT NULL DEFAULT 100
        CHECK (coverage_percent BETWEEN 0 AND 100),
    PRIMARY KEY (control_id, requirement_id)
);

CREATE TABLE compliance_assessments (
    compliance_assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    requirement_id UUID NOT NULL REFERENCES compliance_requirements(requirement_id) ON DELETE CASCADE,
    status VARCHAR(25) NOT NULL
        CHECK (status IN ('COMPLIANT','PARTIAL','NON_COMPLIANT','NOT_APPLICABLE')),
    evidence TEXT,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 7. SCENARIO SIMULATION
-- =========================================================

CREATE TABLE scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    scenario_name VARCHAR(200) NOT NULL,
    description TEXT,
    budget NUMERIC(18,2) CHECK (budget IS NULL OR budget >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scenario_actions (
    scenario_action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(asset_id) ON DELETE CASCADE,
    selected BOOLEAN NOT NULL DEFAULT TRUE,
    assumed_effectiveness_percent NUMERIC(5,2)
        CHECK (assumed_effectiveness_percent IS NULL OR assumed_effectiveness_percent BETWEEN 0 AND 100),
    assumed_cost NUMERIC(18,2) CHECK (assumed_cost IS NULL OR assumed_cost >= 0)
);

CREATE TABLE scenario_results (
    scenario_result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    baseline_eal NUMERIC(18,2) NOT NULL DEFAULT 0,
    projected_eal NUMERIC(18,2) NOT NULL DEFAULT 0,
    risk_reduction NUMERIC(18,2) GENERATED ALWAYS AS
        (baseline_eal - projected_eal) STORED,
    investment_cost NUMERIC(18,2) NOT NULL DEFAULT 0,
    rosi_percent NUMERIC(10,2),
    simulated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 8. INVESTMENT OPTIMIZATION
-- =========================================================

CREATE TABLE investment_options (
    investment_option_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(asset_id) ON DELETE CASCADE,
    estimated_cost NUMERIC(18,2) NOT NULL CHECK (estimated_cost >= 0),
    expected_loss_reduction NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (expected_loss_reduction >= 0),

    -- ROSI = ((risk reduction - cost) / cost) * 100
    rosi_percent NUMERIC(12,2) GENERATED ALWAYS AS (
        CASE
            WHEN estimated_cost = 0 THEN NULL
            ELSE ((expected_loss_reduction - estimated_cost) / estimated_cost) * 100
        END
    ) STORED,

    priority_score NUMERIC(10,2) DEFAULT 0
);

CREATE TABLE optimization_runs (
    optimization_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    budget NUMERIC(18,2) NOT NULL CHECK (budget >= 0),
    algorithm VARCHAR(80) NOT NULL DEFAULT '0/1 Knapsack',
    total_selected_cost NUMERIC(18,2) DEFAULT 0,
    total_expected_loss_reduction NUMERIC(18,2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE optimization_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    optimization_run_id UUID NOT NULL REFERENCES optimization_runs(optimization_run_id) ON DELETE CASCADE,
    investment_option_id UUID NOT NULL REFERENCES investment_options(investment_option_id) ON DELETE CASCADE,
    rank_no INTEGER,
    selected BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT,
    UNIQUE (optimization_run_id, investment_option_id)
);

-- =========================================================
-- 9. DATA INGESTION
-- =========================================================

CREATE TABLE ingestion_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    source_name VARCHAR(150) NOT NULL,
    source_type VARCHAR(30) NOT NULL
        CHECK (source_type IN ('API','CSV','JSON','SIEM','SCANNER','MANUAL')),
    endpoint TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ingested_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES ingestion_sources(source_id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(asset_id) ON DELETE SET NULL,
    event_type VARCHAR(100),
    severity VARCHAR(20)
        CHECK (severity IS NULL OR severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')),
    raw_data JSONB NOT NULL,
    normalized_data JSONB,
    occurred_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_source ON ingested_events(source_id);
CREATE INDEX idx_events_asset ON ingested_events(asset_id);
CREATE INDEX idx_events_raw_data_gin ON ingested_events USING GIN(raw_data);

-- =========================================================
-- 10. AUDIT LOGS
-- =========================================================

CREATE TABLE audit_logs (
    audit_id BIGSERIAL PRIMARY KEY,
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_org_date ON audit_logs(organization_id, created_at DESC);

-- =========================================================
-- 11. USEFUL VIEWS
-- =========================================================

CREATE VIEW organization_risk_summary AS
SELECT
    organization_id,
    COUNT(*) AS assessment_count,
    COALESCE(SUM(expected_annual_loss), 0) AS total_expected_annual_loss,
    COALESCE(MAX(expected_annual_loss), 0) AS highest_single_risk_eal,
    MAX(assessment_date) AS last_assessment_at
FROM risk_assessments
GROUP BY organization_id;

CREATE VIEW optimization_option_summary AS
SELECT
    io.investment_option_id,
    io.organization_id,
    sc.control_name,
    a.asset_name,
    io.estimated_cost,
    io.expected_loss_reduction,
    io.rosi_percent,
    io.priority_score
FROM investment_options io
JOIN security_controls sc ON sc.control_id = io.control_id
LEFT JOIN assets a ON a.asset_id = io.asset_id;

-- =========================================================
-- 12. SAMPLE / SEED DATA
-- =========================================================

INSERT INTO compliance_frameworks (framework_code, framework_name, version)
VALUES
('ISO27001', 'ISO/IEC 27001', '2022'),
('NIST-CSF', 'NIST Cybersecurity Framework', '2.0'),
('CIS', 'CIS Controls', 'v8'),
('RBI-CSF', 'RBI Cyber Security Framework', NULL),
('SEBI-CSCRF', 'SEBI Cybersecurity and Cyber Resilience Framework', NULL)
ON CONFLICT (framework_code) DO NOTHING;

INSERT INTO threats (threat_name, category, description, default_probability)
VALUES
('Ransomware', 'Malware', 'Encryption/extortion attack affecting business systems.', 0.150000),
('Phishing', 'Social Engineering', 'Credential theft through deceptive messages.', 0.350000),
('Data Breach', 'Confidentiality', 'Unauthorized disclosure of sensitive information.', 0.100000),
('DDoS', 'Availability', 'Service disruption through traffic flooding.', 0.080000);

INSERT INTO security_controls
(control_code, control_name, category, description, implementation_cost, annual_maintenance_cost, effectiveness_percent)
VALUES
('CTRL-MFA', 'Multi-Factor Authentication', 'Identity', 'Require multiple factors for user authentication.', 500000, 100000, 60),
('CTRL-EDR', 'Endpoint Detection and Response', 'Endpoint Security', 'Detect and respond to endpoint threats.', 1500000, 400000, 70),
('CTRL-BACKUP', 'Immutable Backup', 'Resilience', 'Maintain protected backups for recovery.', 1000000, 250000, 75),
('CTRL-AWARE', 'Security Awareness Training', 'People', 'Train users to recognize and report threats.', 300000, 100000, 40)
ON CONFLICT (control_code) DO NOTHING;

-- =========================================================
-- 13. EXAMPLE QUERIES
-- =========================================================

-- Total current EAL by organization:
-- SELECT * FROM organization_risk_summary;

-- Highest risk assets:
-- SELECT a.asset_name, SUM(r.expected_annual_loss) AS total_eal
-- FROM risk_assessments r
-- JOIN assets a ON a.asset_id = r.asset_id
-- GROUP BY a.asset_name
-- ORDER BY total_eal DESC;

-- Best security investments by ROSI:
-- SELECT * FROM optimization_option_summary
-- ORDER BY rosi_percent DESC NULLS LAST;

-- Compliance status:
-- SELECT cf.framework_name, ca.status, COUNT(*)
-- FROM compliance_assessments ca
-- JOIN compliance_requirements cr ON cr.requirement_id = ca.requirement_id
-- JOIN compliance_frameworks cf ON cf.framework_id = cr.framework_id
-- GROUP BY cf.framework_name, ca.status
-- ORDER BY cf.framework_name, ca.status;
