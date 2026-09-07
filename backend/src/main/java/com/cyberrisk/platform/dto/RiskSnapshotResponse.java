package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.RiskSnapshot;

import java.math.BigDecimal;
import java.time.Instant;

public record RiskSnapshotResponse(
        String assetId,
        BigDecimal annualizedRateOfOccurrence,
        BigDecimal singleLossExpectancy,
        BigDecimal expectedAnnualLoss,
        BigDecimal valueAtRisk95,
        int openFindingsCount,
        Instant calculatedAt
) {
    public static RiskSnapshotResponse from(RiskSnapshot s) {
        return new RiskSnapshotResponse(
                s.getAsset().getId(),
                s.getAnnualizedRateOfOccurrence(),
                s.getSingleLossExpectancy(),
                s.getExpectedAnnualLoss(),
                s.getValueAtRisk95(),
                s.getOpenFindingsCount(),
                s.getCalculatedAt()
        );
    }
}