package com.cyberrisk.platform.domain;

/**
 * Business-criticality tier for an asset. The weight scales technical
 * findings on the asset into business-relevant impact (higher tier ->
 * larger share of dependent business value is exposed per incident).
 */
public enum AssetCriticality {
    LOW(0.25),
    MEDIUM(0.5),
    HIGH(0.75),
    CRITICAL(1.0);

    private final double weight;

    AssetCriticality(double weight) {
        this.weight = weight;
    }

    public double getWeight() {
        return weight;
    }
}
