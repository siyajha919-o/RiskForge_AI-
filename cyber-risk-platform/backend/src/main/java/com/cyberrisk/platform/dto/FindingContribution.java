package com.cyberrisk.platform.dto;

import java.math.BigDecimal;
import java.util.UUID;

/** How much a single open finding contributes to an asset's expected annual loss. */
public record FindingContribution(
        UUID vulnerabilityId,
        String title,
        String cveId,
        Double cvssScore,
        BigDecimal likelihood,
        BigDecimal impact,
        BigDecimal contributionToExpectedAnnualLoss
) {
}
