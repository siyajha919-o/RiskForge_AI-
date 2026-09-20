package com.cyberrisk.platform.service;

/**
 * Tunable coefficients for the heuristic FAIR-inspired risk model. These are
 * defaults for a prototype -- in production they should be calibrated
 * against organizational incident history and industry loss data (e.g.
 * Verizon DBIR, Ponemon Cost of a Data Breach).
 */
public final class RiskModelConstants {

    private RiskModelConstants() {
    }

    /** Max annual exploitation probability implied by a CVSS 10.0 finding with no exploitability data. */
    public static final double MAX_BASE_ANNUAL_PROBABILITY = 0.35;

    /** Minimum fraction of at-risk business value lost in a low-severity incident. */
    public static final double MIN_SEVERITY_IMPACT_FACTOR = 0.05;

    /** Maximum fraction of at-risk business value lost in a critical-severity incident. */
    public static final double MAX_SEVERITY_IMPACT_FACTOR = 0.5;

    /** Approximate average cost per breached sensitive record (industry benchmark, USD). */
    public static final double COST_PER_RECORD = 150.0;

    /** Monte Carlo iterations used to estimate Value at Risk. */
    public static final int SIMULATION_ITERATIONS = 10_000;

    /** Percentile used for the reported Value at Risk figure. */
    public static final double VALUE_AT_RISK_PERCENTILE = 0.95;

    public static double severityImpactFactor(double cvssScore) {
        double normalized = clamp(cvssScore / 10.0, 0.0, 1.0);
        return MIN_SEVERITY_IMPACT_FACTOR
                + normalized * (MAX_SEVERITY_IMPACT_FACTOR - MIN_SEVERITY_IMPACT_FACTOR);
    }

    public static double baseAnnualProbability(double cvssScore) {
        return clamp(cvssScore / 10.0, 0.0, 1.0) * MAX_BASE_ANNUAL_PROBABILITY;
    }

    public static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }
}
