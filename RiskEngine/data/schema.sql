-- ============================================================================
-- AI-Powered Cyber Risk Quantification & Investment Optimization Platform
-- PostgreSQL Schema
-- ============================================================================

CREATE TABLE organizations (
    organization_id           VARCHAR(15) PRIMARY KEY,
    organization_name         VARCHAR(200) NOT NULL,
    industry                  VARCHAR(50),
    organization_size         VARCHAR(20),
    annual_revenue            BIGINT,
    employee_count            INTEGER,
    country                   VARCHAR(50),
    regulatory_category       VARCHAR(50),
    security_budget           BIGINT,
    annual_IT_budget          BIGINT,
    cyber_maturity_score      NUMERIC(3,1),
    overall_risk_tolerance    VARCHAR(20)
);

CREATE TABLE business_units (
    business_unit_id              VARCHAR(15) PRIMARY KEY,
    organization_id                VARCHAR(15) REFERENCES organizations(organization_id),
    business_unit_name             VARCHAR(100),
    business_function              VARCHAR(50),
    annual_revenue_contribution    BIGINT,
    employee_count                 INTEGER,
    criticality_score              INTEGER CHECK (criticality_score BETWEEN 1 AND 10),
    maximum_tolerable_downtime_hours INTEGER,
    data_sensitivity               VARCHAR(30),
    regulatory_importance          VARCHAR(20)
);

CREATE TABLE assets (
    asset_id                VARCHAR(15) PRIMARY KEY,
    organization_id         VARCHAR(15) REFERENCES organizations(organization_id),
    business_unit_id        VARCHAR(15) REFERENCES business_units(business_unit_id),
    asset_name               VARCHAR(150),
    asset_type               VARCHAR(50),
    operating_system         VARCHAR(50),
    environment               VARCHAR(20),
    cloud_provider            VARCHAR(20),
    region                    VARCHAR(30),
    internet_exposed          BOOLEAN,
    asset_owner               VARCHAR(100),
    business_service          VARCHAR(100),
    data_classification       VARCHAR(30),
    asset_criticality         VARCHAR(20),
    confidentiality_score     INTEGER,
    integrity_score           INTEGER,
    availability_score        INTEGER,
    revenue_dependency        NUMERIC(4,2),
    customer_dependency       NUMERIC(4,2),
    regulatory_dependency     NUMERIC(4,2),
    dependency_count          INTEGER,
    asset_age_days            INTEGER,
    current_risk_score        NUMERIC(4,1)
);

CREATE TABLE vulnerabilities (
    vulnerability_id          VARCHAR(15) PRIMARY KEY,
    asset_id                  VARCHAR(15) REFERENCES assets(asset_id),
    cve_id                    VARCHAR(30),
    vulnerability_type        VARCHAR(50),
    cvss_score                NUMERIC(3,1),
    severity                  VARCHAR(20),
    exploitability_score      NUMERIC(3,1),
    attack_vector              VARCHAR(20),
    attack_complexity          VARCHAR(10),
    privileges_required        VARCHAR(10),
    user_interaction            VARCHAR(15),
    known_exploited            BOOLEAN,
    exploit_available           BOOLEAN,
    exploit_age_days            INTEGER,
    vulnerability_age_days      INTEGER,
    affected_service             VARCHAR(50),
    patch_available              BOOLEAN,
    patch_age_days               INTEGER,
    remediation_status            VARCHAR(20),
    remediation_deadline          DATE,
    vulnerability_risk_score      NUMERIC(4,1)
);

CREATE TABLE threat_intelligence (
    threat_id                  VARCHAR(15) PRIMARY KEY,
    threat_actor                VARCHAR(50),
    threat_category              VARCHAR(50),
    attack_technique              VARCHAR(80),
    targeted_industry              VARCHAR(50),
    targeted_asset_type            VARCHAR(50),
    campaign_active                 BOOLEAN,
    threat_frequency                 INTEGER,
    exploit_probability               NUMERIC(4,2),
    geographic_scope                   VARCHAR(30),
    severity                            VARCHAR(20),
    intelligence_confidence             VARCHAR(20),
    first_seen                           DATE,
    last_seen                            DATE,
    associated_cve                        VARCHAR(30),
    ransomware_indicator                  BOOLEAN,
    data_exfiltration_risk                BOOLEAN
);

CREATE TABLE security_controls (
    control_id                  VARCHAR(15) PRIMARY KEY,
    organization_id              VARCHAR(15) REFERENCES organizations(organization_id),
    control_name                  VARCHAR(100),
    control_category               VARCHAR(50),
    implementation_status           VARCHAR(30),
    coverage_percentage              INTEGER,
    effectiveness_score              NUMERIC(4,2),
    maturity_level                   VARCHAR(20),
    annual_cost                       BIGINT,
    implementation_cost               BIGINT,
    maintenance_cost                  BIGINT,
    deployment_time_days               INTEGER,
    risk_reduction_percentage          NUMERIC(5,1),
    compliance_status                  VARCHAR(20),
    last_assessment_date                DATE
);

CREATE TABLE asset_controls (
    asset_control_id             VARCHAR(15) PRIMARY KEY,
    asset_id                      VARCHAR(15) REFERENCES assets(asset_id),
    control_id                     VARCHAR(15) REFERENCES security_controls(control_id),
    enabled                         BOOLEAN,
    coverage_percentage              INTEGER,
    effectiveness_score              NUMERIC(4,2),
    last_verified                    DATE,
    configuration_score              NUMERIC(4,2),
    control_failure_count            INTEGER,
    residual_risk                     NUMERIC(5,2)
);

CREATE TABLE security_incidents (
    incident_id                  VARCHAR(15) PRIMARY KEY,
    organization_id               VARCHAR(15) REFERENCES organizations(organization_id),
    asset_id                       VARCHAR(15) REFERENCES assets(asset_id),
    business_unit_id                VARCHAR(15) REFERENCES business_units(business_unit_id),
    threat_id                        VARCHAR(15) REFERENCES threat_intelligence(threat_id),
    incident_type                     VARCHAR(50),
    attack_vector                      VARCHAR(50),
    detection_time                      INTEGER,
    response_time                        INTEGER,
    resolution_time                      INTEGER,
    downtime_hours                        INTEGER,
    data_records_affected                 BIGINT,
    incident_severity                      VARCHAR(20),
    direct_financial_loss                   BIGINT,
    recovery_cost                            BIGINT,
    legal_cost                                BIGINT,
    regulatory_penalty                         BIGINT,
    customer_compensation                       BIGINT,
    reputation_loss                              BIGINT,
    total_financial_loss                          BIGINT,
    control_failure                                VARCHAR(50),
    incident_resolved                               BOOLEAN
);

CREATE TABLE business_impact (
    impact_id                    VARCHAR(15) PRIMARY KEY,
    asset_id                      VARCHAR(15) REFERENCES assets(asset_id),
    business_unit_id                VARCHAR(15) REFERENCES business_units(business_unit_id),
    revenue_per_hour                 BIGINT,
    downtime_cost_per_hour             BIGINT,
    customer_impact_cost                BIGINT,
    data_record_cost                     INTEGER,
    regulatory_penalty_estimate           BIGINT,
    legal_cost_estimate                    BIGINT,
    recovery_cost_estimate                  BIGINT,
    reputation_impact_cost                   BIGINT,
    productivity_loss_per_hour                BIGINT,
    maximum_tolerable_loss                     BIGINT,
    estimated_total_impact                      BIGINT
);

CREATE TABLE iam_risk (
    iam_event_id                 VARCHAR(15) PRIMARY KEY,
    organization_id                VARCHAR(15) REFERENCES organizations(organization_id),
    asset_id                        VARCHAR(15) REFERENCES assets(asset_id),
    user_count                       INTEGER,
    privileged_user_count             INTEGER,
    orphan_accounts                    INTEGER,
    inactive_accounts                   INTEGER,
    mfa_enabled_percentage               INTEGER,
    excessive_privilege_count             INTEGER,
    failed_login_count                     INTEGER,
    suspicious_login_count                  INTEGER,
    password_policy_score                    NUMERIC(4,2),
    privileged_access_risk                    VARCHAR(20),
    identity_risk_score                        NUMERIC(4,1)
);

CREATE TABLE edr_telemetry (
    telemetry_id                 VARCHAR(15) PRIMARY KEY,
    asset_id                      VARCHAR(15) REFERENCES assets(asset_id),
    timestamp                      TIMESTAMP,
    malware_detected                BOOLEAN,
    suspicious_process_count          INTEGER,
    endpoint_alert_count               INTEGER,
    ransomware_indicator                 BOOLEAN,
    malicious_file_count                  INTEGER,
    blocked_connection_count               INTEGER,
    isolation_triggered                     BOOLEAN,
    detection_confidence                     NUMERIC(4,2),
    endpoint_security_score                   NUMERIC(4,1)
);

CREATE TABLE cloud_security (
    cloud_event_id                VARCHAR(15) PRIMARY KEY,
    asset_id                       VARCHAR(15) REFERENCES assets(asset_id),
    cloud_provider                  VARCHAR(20),
    service_type                     VARCHAR(30),
    public_exposure                   BOOLEAN,
    misconfiguration_type              VARCHAR(50),
    encryption_enabled                  BOOLEAN,
    logging_enabled                      BOOLEAN,
    iam_risk                              VARCHAR(20),
    open_port_count                        INTEGER,
    exposed_storage                         BOOLEAN,
    compliance_violation                     BOOLEAN,
    cloud_risk_score                          NUMERIC(4,1)
);

CREATE TABLE compliance_mapping (
    mapping_id                    VARCHAR(15) PRIMARY KEY,
    organization_id                 VARCHAR(15) REFERENCES organizations(organization_id),
    control_id                       VARCHAR(15) REFERENCES security_controls(control_id),
    framework                         VARCHAR(80),
    framework_function                 VARCHAR(50),
    framework_category                  VARCHAR(80),
    requirement_id                       VARCHAR(30),
    compliance_status                     VARCHAR(30),
    evidence_available                     BOOLEAN,
    evidence_quality                        VARCHAR(20),
    gap_score                                NUMERIC(4,2)
);

CREATE TABLE remediation_actions (
    remediation_id                VARCHAR(15) PRIMARY KEY,
    vulnerability_id               VARCHAR(15) REFERENCES vulnerabilities(vulnerability_id),
    asset_id                        VARCHAR(15) REFERENCES assets(asset_id),
    recommended_action                VARCHAR(80),
    action_category                    VARCHAR(50),
    estimated_cost                      BIGINT,
    implementation_time_days             INTEGER,
    expected_risk_reduction               NUMERIC(5,1),
    expected_loss_reduction                BIGINT,
    priority                                VARCHAR(20),
    required_control                        VARCHAR(15),
    dependency                               VARCHAR(80),
    recommended_deadline                      DATE,
    status                                     VARCHAR(20)
);

CREATE TABLE investment_options (
    investment_id                 VARCHAR(15) PRIMARY KEY,
    organization_id                 VARCHAR(15) REFERENCES organizations(organization_id),
    control_id                       VARCHAR(15) REFERENCES security_controls(control_id),
    investment_name                    VARCHAR(100),
    implementation_cost                 BIGINT,
    annual_operating_cost                BIGINT,
    expected_risk_reduction_percentage    NUMERIC(5,1),
    expected_loss_reduction                BIGINT,
    implementation_time_days                INTEGER,
    affected_assets                          INTEGER,
    affected_business_units                   INTEGER,
    compliance_benefit                         VARCHAR(20),
    implementation_priority                     VARCHAR(20),
    expected_ROSI                                NUMERIC(6,1)
);

CREATE TABLE risk_calculations (
    risk_id                       VARCHAR(15) PRIMARY KEY,
    organization_id                 VARCHAR(15) REFERENCES organizations(organization_id),
    business_unit_id                 VARCHAR(15) REFERENCES business_units(business_unit_id),
    asset_id                          VARCHAR(15) REFERENCES assets(asset_id),
    vulnerability_id                   VARCHAR(15) REFERENCES vulnerabilities(vulnerability_id),
    threat_id                           VARCHAR(15) REFERENCES threat_intelligence(threat_id),
    likelihood_score                     NUMERIC(4,1),
    impact_score                          NUMERIC(4,1),
    inherent_risk                          NUMERIC(5,2),
    control_effectiveness                   NUMERIC(4,2),
    residual_risk                            NUMERIC(5,2),
    incident_probability                      NUMERIC(6,4),
    single_loss_expectancy                     BIGINT,
    annual_rate_of_occurrence                   NUMERIC(6,3),
    expected_annual_loss                         BIGINT,
    value_at_risk                                 BIGINT,
    financial_exposure                             BIGINT,
    risk_reduction_potential                        NUMERIC(5,2),
    current_security_spend                           BIGINT,
    recommended_security_spend                        BIGINT,
    risk_score                                         NUMERIC(4,2)
);

CREATE TABLE optimization_results (
    scenario_id                   VARCHAR(15) PRIMARY KEY,
    organization_id                 VARCHAR(15) REFERENCES organizations(organization_id),
    budget                            BIGINT,
    selected_controls                  INTEGER,
    selected_remediations               TEXT,
    total_investment                     BIGINT,
    initial_EAL                           BIGINT,
    projected_EAL                          BIGINT,
    total_risk_reduction                    NUMERIC(6,1),
    risk_reduction_percentage                NUMERIC(5,1),
    expected_loss_avoided                     BIGINT,
    ROSI                                       NUMERIC(6,1),
    ROI                                         NUMERIC(6,2),
    optimization_score                           NUMERIC(5,1)
);

-- ============================================================================
-- Indexes for common query patterns
-- ============================================================================
CREATE INDEX idx_assets_org ON assets(organization_id);
CREATE INDEX idx_assets_bu ON assets(business_unit_id);
CREATE INDEX idx_assets_crit ON assets(asset_criticality);
CREATE INDEX idx_vuln_asset ON vulnerabilities(asset_id);
CREATE INDEX idx_vuln_severity ON vulnerabilities(severity);
CREATE INDEX idx_vuln_cve ON vulnerabilities(cve_id);
CREATE INDEX idx_incidents_org ON security_incidents(organization_id);
CREATE INDEX idx_incidents_asset ON security_incidents(asset_id);
CREATE INDEX idx_risk_org ON risk_calculations(organization_id);
CREATE INDEX idx_risk_asset ON risk_calculations(asset_id);
CREATE INDEX idx_risk_eal ON risk_calculations(expected_annual_loss DESC);
CREATE INDEX idx_remediation_status ON remediation_actions(status);
CREATE INDEX idx_investment_org ON investment_options(organization_id);
CREATE INDEX idx_optimization_org ON optimization_results(organization_id);
