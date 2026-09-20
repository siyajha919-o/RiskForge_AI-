package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.ControlType;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

public record ControlRequest(
        @NotNull UUID assetId,
        @NotBlank String name,
        String description,
        @NotNull ControlType controlType,
        @NotNull @DecimalMin("0.0") @DecimalMax("1.0") Double effectivenessScore,
        boolean implemented,
        BigDecimal annualCost,
        List<String> frameworkMappings
) {
}
