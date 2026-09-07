package com.cyberrisk.platform.service;

/**
 * Constants and helper methods used by the
 * RiskForge AI risk quantification model.
 */
public final class RiskModelConstants {

    private RiskModelConstants() {
        // Prevent object creation
    }

    /**
     * Maximum annual exploitation probability
     * for a CVSS score of 10.
     */
    public static final double MAX_BASE_ANNUAL_PROBABILITY = 0.35;

    /**
     * Minimum impact factor for low-severity risks.
     */
    public static final double MIN_SEVERITY_IMPACT_FACTOR = 0.05;

    /**
     * Maximum impact factor for critical risks.
     */
    public static final double MAX_SEVERITY_IMPACT_FACTOR = 0.50;

    /**
     * Estimated financial cost per compromised
     * sensitive record.
     */
    public static final double COST_PER_RECORD = 150.0;

    /**
     * Number of Monte Carlo simulation iterations.
     */
    public static final int SIMULATION_ITERATIONS = 10_000;

    /**
     * Value at Risk percentile (95%).
     */
    public static final double VALUE_AT_RISK_PERCENTILE = 0.95;

    /**
     * Convert CVSS score into an impact factor.
     */
    public static double severityImpactFactor(double cvssScore) {

        double normalized = clamp(
                cvssScore / 10.0,
                0.0,
                1.0
        );

        return MIN_SEVERITY_IMPACT_FACTOR
                + normalized
                * (MAX_SEVERITY_IMPACT_FACTOR
                - MIN_SEVERITY_IMPACT_FACTOR);
    }

    /**
     * Estimate annual exploitation probability
     * using the CVSS score.
     */
    public static double baseAnnualProbability(double cvssScore) {

        double normalized = clamp(
                cvssScore / 10.0,
                0.0,
                1.0
        );

        return normalized
                * MAX_BASE_ANNUAL_PROBABILITY;
    }

    /**
     * Keep a value inside a specified range.
     */
    public static double clamp(
            double value,
            double min,
            double max
    ) {

        return Math.max(
                min,
                Math.min(max, value)
        );
    }
}