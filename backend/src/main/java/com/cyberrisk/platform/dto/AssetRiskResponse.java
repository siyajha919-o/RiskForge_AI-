package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.AssetCriticality;

import java.math.BigDecimal;
import java.util.List;

public record AssetRiskResponse(
        String assetId,
        String assetName,
        String businessUnit,
        AssetCriticality criticality,
        int openFindingsCount,
        BigDecimal annualizedRateOfOccurrence,
        BigDecimal singleLossExpectancy,
        BigDecimal expectedAnnualLoss,
        BigDecimal valueAtRisk95,
        List<FindingContribution> topContributors
) {
}
