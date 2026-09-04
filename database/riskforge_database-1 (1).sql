-- RiskForge_AI PostgreSQL Database
-- Project-aligned schema based on the public RiskForge_AI README.
-- Requires PostgreSQL 14+ and pgcrypto for UUID generation.

BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN CREATE TYPE user_role AS ENUM ('admin','analyst','viewer','compliance'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE asset_criticality AS ENUM ('low','medium','high','critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE severity_level AS ENUM ('low','medium','high','critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE record_status AS ENUM ('active','inactive','resolved','open','accepted'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE compliance_status AS ENUM ('not_assessed','compliant','partial','non_compliant','not_applicable'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE ingestion_status AS ENUM ('pending','processing','completed','failed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS organizations (
  organization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL UNIQUE,
  industry VARCHAR(120), country VARCHAR(100),
  annual_revenue NUMERIC(18,2) CHECK (annual_revenue IS NULL OR annual_revenue >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  email VARCHAR(320) NOT NULL, full_name VARCHAR(160), password_hash TEXT NOT NULL,
  role user_role NOT NULL DEFAULT 'viewer', is_active BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id,email)
);

CREATE TABLE IF NOT EXISTS assets (
  asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  asset_name VARCHAR(200) NOT NULL, asset_type VARCHAR(100) NOT NULL, description TEXT,
  owner_name VARCHAR(160), business_unit VARCHAR(160), criticality asset_criticality NOT NULL DEFAULT 'medium',
  asset_value NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (asset_value >= 0),
  confidentiality_score SMALLINT CHECK (confidentiality_score BETWEEN 1 AND 5),
  integrity_score SMALLINT CHECK (integrity_score BETWEEN 1 AND 5),
  availability_score SMALLINT CHECK (availability_score BETWEEN 1 AND 5),
  is_internet_facing BOOLEAN NOT NULL DEFAULT FALSE, status record_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id,asset_name)
);

CREATE TABLE IF NOT EXISTS threats (
  threat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  threat_name VARCHAR(200) NOT NULL, category VARCHAR(120), description TEXT,
  base_probability NUMERIC(8,6) CHECK (base_probability BETWEEN 0 AND 1),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (organization_id,threat_name)
);

CREATE TABLE IF NOT EXISTS vulnerabilities (
  vulnerability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  cve_id VARCHAR(32), title VARCHAR(255) NOT NULL, description TEXT, severity severity_level NOT NULL,
  cvss_score NUMERIC(3,1) CHECK (cvss_score IS NULL OR cvss_score BETWEEN 0 AND 10),
  exploit_available BOOLEAN NOT NULL DEFAULT FALSE, discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  due_date DATE, status record_status NOT NULL DEFAULT 'open', source VARCHAR(120),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asset_threats (
  asset_threat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  threat_id UUID NOT NULL REFERENCES threats(threat_id) ON DELETE CASCADE,
  likelihood NUMERIC(8,6) NOT NULL CHECK (likelihood BETWEEN 0 AND 1), notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(asset_id,threat_id)
);

CREATE TABLE IF NOT EXISTS risk_assessments (
  risk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  asset_id UUID NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
  threat_id UUID REFERENCES threats(threat_id) ON DELETE SET NULL,
  vulnerability_id UUID REFERENCES vulnerabilities(vulnerability_id) ON DELETE SET NULL,
  annual_probability NUMERIC(8,6) NOT NULL CHECK (annual_probability BETWEEN 0 AND 1),
  single_loss_expectancy NUMERIC(18,2) NOT NULL CHECK (single_loss_expectancy >= 0),
  eal NUMERIC(18,2) GENERATED ALWAYS AS (annual_probability * single_loss_expectancy) STORED,
  value_at_risk NUMERIC(18,2) CHECK (value_at_risk IS NULL OR value_at_risk >= 0),
  confidence_level NUMERIC(5,4) CHECK (confidence_level IS NULL OR confidence_level > 0 AND confidence_level < 1),
  risk_score NUMERIC(10,4) CHECK (risk_score IS NULL OR risk_score >= 0),
  model_version VARCHAR(80), assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
  assessed_by UUID REFERENCES users(user_id) ON DELETE SET NULL, assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security_controls (
  control_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
  control_code VARCHAR(80), control_name VARCHAR(255) NOT NULL, category VARCHAR(120), description TEXT,
  implementation_cost NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (implementation_cost >= 0),
  annual_operating_cost NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (annual_operating_cost >= 0),
  effectiveness NUMERIC(8,6) NOT NULL DEFAULT 0 CHECK (effectiveness BETWEEN 0 AND 1),
  is_implemented BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_control_mappings (
  mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  risk_id UUID NOT NULL REFERENCES risk_assessments(risk_id) ON DELETE CASCADE,
  control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
  expected_reduction_pct NUMERIC(8,6) NOT NULL CHECK (expected_reduction_pct BETWEEN 0 AND 1),
  estimated_residual_eal NUMERIC(18,2) CHECK (estimated_residual_eal IS NULL OR estimated_residual_eal >= 0),
  estimated_annual_benefit NUMERIC(18,2) CHECK (estimated_annual_benefit IS NULL OR estimated_annual_benefit >= 0),
  rosi NUMERIC(18,6), notes TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(risk_id,control_id)
);

CREATE TABLE IF NOT EXISTS scenarios (
  scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  scenario_name VARCHAR(255) NOT NULL, description TEXT, created_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scenario_controls (
  scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
  control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
  PRIMARY KEY(scenario_id,control_id)
);

CREATE TABLE IF NOT EXISTS scenario_results (
  result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), scenario_id UUID NOT NULL REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
  baseline_eal NUMERIC(18,2) NOT NULL CHECK (baseline_eal >= 0), residual_eal NUMERIC(18,2) NOT NULL CHECK (residual_eal >= 0),
  risk_reduction NUMERIC(18,2) GENERATED ALWAYS AS (baseline_eal - residual_eal) STORED,
  total_control_cost NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK(total_control_cost >= 0), rosi NUMERIC(18,6),
  simulation_parameters JSONB NOT NULL DEFAULT '{}'::jsonb, computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS optimization_runs (
  optimization_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL, budget NUMERIC(18,2) NOT NULL CHECK(budget >= 0),
  objective VARCHAR(100) NOT NULL DEFAULT 'maximize_risk_reduction', algorithm VARCHAR(100) NOT NULL DEFAULT '0_1_knapsack',
  parameters JSONB NOT NULL DEFAULT '{}'::jsonb, total_selected_cost NUMERIC(18,2), expected_risk_reduction NUMERIC(18,2),
  expected_residual_eal NUMERIC(18,2), status VARCHAR(40) NOT NULL DEFAULT 'completed',
  created_by UUID REFERENCES users(user_id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS optimization_recommendations (
  recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  optimization_run_id UUID NOT NULL REFERENCES optimization_runs(optimization_run_id) ON DELETE CASCADE,
  control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
  rank_order INTEGER CHECK(rank_order IS NULL OR rank_order > 0), control_cost NUMERIC(18,2) NOT NULL CHECK(control_cost >= 0),
  expected_risk_reduction NUMERIC(18,2) NOT NULL CHECK(expected_risk_reduction >= 0), estimated_rosi NUMERIC(18,6),
  selected BOOLEAN NOT NULL DEFAULT TRUE, rationale TEXT, UNIQUE(optimization_run_id,control_id)
);

CREATE TABLE IF NOT EXISTS compliance_frameworks (
  framework_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), framework_code VARCHAR(50) NOT NULL UNIQUE,
  framework_name VARCHAR(255) NOT NULL, version VARCHAR(80), description TEXT, official_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS compliance_requirements (
  requirement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), framework_id UUID NOT NULL REFERENCES compliance_frameworks(framework_id) ON DELETE CASCADE,
  requirement_code VARCHAR(100) NOT NULL, title VARCHAR(255) NOT NULL, description TEXT, category VARCHAR(160),
  parent_requirement_id UUID REFERENCES compliance_requirements(requirement_id) ON DELETE SET NULL,
  UNIQUE(framework_id,requirement_code)
);

CREATE TABLE IF NOT EXISTS control_compliance_mappings (
  control_id UUID NOT NULL REFERENCES security_controls(control_id) ON DELETE CASCADE,
  requirement_id UUID NOT NULL REFERENCES compliance_requirements(requirement_id) ON DELETE CASCADE,
  mapping_strength NUMERIC(4,3) NOT NULL DEFAULT 1 CHECK(mapping_strength BETWEEN 0 AND 1), mapping_notes TEXT,
  PRIMARY KEY(control_id,requirement_id)
);

CREATE TABLE IF NOT EXISTS compliance_assessments (
  assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  requirement_id UUID NOT NULL REFERENCES compliance_requirements(requirement_id) ON DELETE CASCADE,
  status compliance_status NOT NULL DEFAULT 'not_assessed', score NUMERIC(5,2) CHECK(score IS NULL OR score BETWEEN 0 AND 100),
  gap_description TEXT, remediation_plan TEXT, assessed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
  assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), next_review_date DATE, UNIQUE(organization_id,requirement_id)
);

CREATE TABLE IF NOT EXISTS compliance_evidence (
  evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), assessment_id UUID NOT NULL REFERENCES compliance_assessments(assessment_id) ON DELETE CASCADE,
  evidence_type VARCHAR(100) NOT NULL, evidence_name VARCHAR(255) NOT NULL, evidence_uri TEXT, description TEXT,
  collected_by UUID REFERENCES users(user_id) ON DELETE SET NULL, collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
  ingestion_job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
  source_type VARCHAR(80) NOT NULL, source_name VARCHAR(200), filename VARCHAR(255), status ingestion_status NOT NULL DEFAULT 'pending',
  total_records INTEGER NOT NULL DEFAULT 0 CHECK(total_records >= 0), successful_records INTEGER NOT NULL DEFAULT 0 CHECK(successful_records >= 0),
  failed_records INTEGER NOT NULL DEFAULT 0 CHECK(failed_records >= 0), error_message TEXT, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  created_by UUID REFERENCES users(user_id) ON DELETE SET NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestion_errors (
  error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), ingestion_job_id UUID NOT NULL REFERENCES ingestion_jobs(ingestion_job_id) ON DELETE CASCADE,
  row_number INTEGER, raw_payload JSONB, error_message TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id BIGSERIAL PRIMARY KEY, organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
  user_id UUID REFERENCES users(user_id) ON DELETE SET NULL, action VARCHAR(120) NOT NULL,
  entity_type VARCHAR(100), entity_id UUID, old_values JSONB, new_values JSONB,
  ip_address INET, user_agent TEXT, success BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_assets_org ON assets(organization_id);
CREATE INDEX IF NOT EXISTS idx_assets_criticality ON assets(criticality);
CREATE INDEX IF NOT EXISTS idx_vulns_asset ON vulnerabilities(asset_id);
CREATE INDEX IF NOT EXISTS idx_vulns_severity ON vulnerabilities(severity);
CREATE INDEX IF NOT EXISTS idx_vulns_status ON vulnerabilities(status);
CREATE INDEX IF NOT EXISTS idx_risk_org ON risk_assessments(organization_id);
CREATE INDEX IF NOT EXISTS idx_risk_asset ON risk_assessments(asset_id);
CREATE INDEX IF NOT EXISTS idx_risk_eal ON risk_assessments(eal DESC);
CREATE INDEX IF NOT EXISTS idx_controls_org ON security_controls(organization_id);
CREATE INDEX IF NOT EXISTS idx_compliance_assessment_org ON compliance_assessments(organization_id);
CREATE INDEX IF NOT EXISTS idx_compliance_assessment_status ON compliance_assessments(status);
CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_logs(organization_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_org_time ON ingestion_jobs(organization_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_assumptions_gin ON risk_assessments USING GIN(assumptions);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at=NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_organizations_updated_at ON organizations;
CREATE TRIGGER trg_organizations_updated_at BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_assets_updated_at ON assets;
CREATE TRIGGER trg_assets_updated_at BEFORE UPDATE ON assets FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_vulnerabilities_updated_at ON vulnerabilities;
CREATE TRIGGER trg_vulnerabilities_updated_at BEFORE UPDATE ON vulnerabilities FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_controls_updated_at ON security_controls;
CREATE TRIGGER trg_controls_updated_at BEFORE UPDATE ON security_controls FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE VIEW v_organization_risk_summary AS
SELECT o.organization_id,o.name AS organization_name,
 COUNT(DISTINCT a.asset_id) AS total_assets,
 COUNT(DISTINCT v.vulnerability_id) FILTER (WHERE v.status='open') AS open_vulnerabilities,
 COUNT(DISTINCT v.vulnerability_id) FILTER (WHERE v.severity='critical' AND v.status='open') AS critical_open_vulnerabilities,
 COALESCE(SUM(r.eal),0) AS total_expected_annual_loss,
 COALESCE(MAX(r.eal),0) AS highest_single_risk_eal
FROM organizations o LEFT JOIN assets a ON a.organization_id=o.organization_id
LEFT JOIN vulnerabilities v ON v.asset_id=a.asset_id LEFT JOIN risk_assessments r ON r.asset_id=a.asset_id
GROUP BY o.organization_id,o.name;

CREATE OR REPLACE VIEW v_compliance_summary AS
SELECT ca.organization_id,cf.framework_code,cf.framework_name,COUNT(*) AS assessed_requirements,
 COUNT(*) FILTER (WHERE ca.status='compliant') AS compliant_count,
 COUNT(*) FILTER (WHERE ca.status='partial') AS partial_count,
 COUNT(*) FILTER (WHERE ca.status='non_compliant') AS non_compliant_count,
 ROUND(100.0*COUNT(*) FILTER(WHERE ca.status='compliant')/NULLIF(COUNT(*) FILTER(WHERE ca.status<>'not_applicable'),0),2) AS simple_compliance_percent
FROM compliance_assessments ca JOIN compliance_requirements cr ON cr.requirement_id=ca.requirement_id
JOIN compliance_frameworks cf ON cf.framework_id=cr.framework_id
GROUP BY ca.organization_id,cf.framework_code,cf.framework_name;

CREATE OR REPLACE VIEW v_control_business_case AS
SELECT rc.mapping_id,r.organization_id,r.risk_id,a.asset_name,sc.control_id,sc.control_name,r.eal AS baseline_eal,
 rc.expected_reduction_pct,
 COALESCE(rc.estimated_residual_eal,r.eal*(1-rc.expected_reduction_pct)) AS residual_eal,
 COALESCE(rc.estimated_annual_benefit,r.eal*rc.expected_reduction_pct) AS expected_annual_benefit,
 sc.implementation_cost,sc.annual_operating_cost,rc.rosi
FROM risk_control_mappings rc JOIN risk_assessments r ON r.risk_id=rc.risk_id
JOIN assets a ON a.asset_id=r.asset_id JOIN security_controls sc ON sc.control_id=rc.control_id;

INSERT INTO compliance_frameworks(framework_code,framework_name,description) VALUES
 ('ISO27001','ISO/IEC 27001','Information security management system framework'),
 ('NIST-CSF','NIST Cybersecurity Framework','Cybersecurity risk management framework'),
 ('CIS','CIS Critical Security Controls','Prioritized cybersecurity safeguards'),
 ('RBI-CSF','RBI Cyber Security Framework','Cybersecurity guidance for regulated Indian financial entities'),
 ('SEBI-CSCRF','SEBI Cybersecurity and Cyber Resilience Framework','Cybersecurity and resilience requirements for regulated securities-market entities')
ON CONFLICT(framework_code) DO NOTHING;

COMMIT;

-- Example dashboard queries:
-- SELECT * FROM v_organization_risk_summary;
-- SELECT * FROM v_compliance_summary;
-- SELECT * FROM v_control_business_case ORDER BY rosi DESC NULLS LAST;
