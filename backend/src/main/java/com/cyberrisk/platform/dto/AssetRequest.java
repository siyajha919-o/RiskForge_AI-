package com.cyberrisk.platform.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

import java.math.BigDecimal;

public record AssetRequest(
        @NotBlank String name,
        @NotNull String assetType,
        String businessUnit,
        @NotNull String criticality,
        @NotNull @PositiveOrZero BigDecimal annualBusinessValue,
        Long sensitiveRecordCount
) {
}
