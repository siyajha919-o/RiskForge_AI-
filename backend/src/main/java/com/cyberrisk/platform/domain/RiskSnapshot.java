package com.cyberrisk.platform.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Point-in-time financial risk calculation for a single asset, persisted so
 * risk trend analysis can be served without recomputing history.
 */
@Entity
@Table(name = "risk_snapshots")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RiskSnapshot {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "asset_id")
    private Asset asset;

    /** Annualized Rate of Occurrence: expected number of loss events per year. */
    @Column(nullable = false)
    private BigDecimal annualizedRateOfOccurrence;

    /** Single Loss Expectancy: expected financial loss per event, averaged across open findings. */
    @Column(nullable = false)
    private BigDecimal singleLossExpectancy;

    /** Annualized Loss Expectancy / Expected Annual Loss = ARO x SLE, summed across findings. */
    @Column(nullable = false)
    private BigDecimal expectedAnnualLoss;

    /** 95th percentile simulated annual loss (Value at Risk). */
    @Column(nullable = false)
    private BigDecimal valueAtRisk95;

    @Column(nullable = false)
    private int openFindingsCount;

    @Builder.Default
    private Instant calculatedAt = Instant.now();
}
