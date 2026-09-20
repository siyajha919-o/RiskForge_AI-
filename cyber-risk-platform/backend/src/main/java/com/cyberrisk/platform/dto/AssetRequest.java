package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.AssetCriticality;
import com.cyberrisk.platform.domain.AssetType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

import java.math.BigDecimal;

public record AssetRequest(
        @NotBlank String name,
        @NotNull AssetType assetType,
        String businessUnit,
        @NotNull AssetCriticality criticality,
        @NotNull @PositiveOrZero BigDecimal annualBusinessValue,
        Long sensitiveRecordCount
) {
}
