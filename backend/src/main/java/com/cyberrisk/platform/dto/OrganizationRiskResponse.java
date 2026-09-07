package com.cyberrisk.platform.dto;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public record OrganizationRiskResponse(
        int assetCount,
        BigDecimal totalExpectedAnnualLoss,
        BigDecimal totalValueAtRisk95,
        Map<String, BigDecimal> expectedAnnualLossByBusinessUnit,
        List<AssetRiskResponse> topRiskyAssets
) {
}
