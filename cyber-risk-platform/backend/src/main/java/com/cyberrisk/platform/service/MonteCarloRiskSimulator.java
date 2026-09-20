package com.cyberrisk.platform.service;

import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Estimates Value at Risk by simulating many possible "loss years": in each
 * iteration, every finding either triggers a loss event (with probability
 * equal to its adjusted annual likelihood) or doesn't, and triggered losses
 * are summed. The requested percentile of the resulting loss distribution is
 * the reported Value at Risk.
 */
@Component
public class MonteCarloRiskSimulator {

    /**
     * @param likelihoods   per-finding annual probability of occurrence (0-1)
     * @param impacts       per-finding expected financial impact if it occurs
     * @param iterations    number of simulated years
     * @param percentile    percentile to report, e.g. 0.95
     */
    public double simulateValueAtRisk(double[] likelihoods, double[] impacts, int iterations, double percentile) {
        if (likelihoods.length == 0) {
            return 0.0;
        }
        ThreadLocalRandom random = ThreadLocalRandom.current();
        double[] totals = new double[iterations];

        for (int i = 0; i < iterations; i++) {
            double total = 0.0;
            for (int f = 0; f < likelihoods.length; f++) {
                if (random.nextDouble() < likelihoods[f]) {
                    // Add variability around the expected impact (+/-50%) to reflect
                    // uncertainty in actual incident severity.
                    double severityMultiplier = 0.5 + random.nextDouble();
                    total += impacts[f] * severityMultiplier;
                }
            }
            totals[i] = total;
        }

        Arrays.sort(totals);
        int index = (int) Math.ceil(percentile * totals.length) - 1;
        index = Math.max(0, Math.min(totals.length - 1, index));
        return totals[index];
    }

    public double simulateValueAtRisk(List<Double> likelihoods, List<Double> impacts) {
        double[] l = likelihoods.stream().mapToDouble(Double::doubleValue).toArray();
        double[] im = impacts.stream().mapToDouble(Double::doubleValue).toArray();
        return simulateValueAtRisk(l, im, RiskModelConstants.SIMULATION_ITERATIONS,
                RiskModelConstants.VALUE_AT_RISK_PERCENTILE);
    }
}
