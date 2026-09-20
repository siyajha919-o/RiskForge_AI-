package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.AssetCriticality;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record AssetRiskResponse(
        UUID assetId,
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
