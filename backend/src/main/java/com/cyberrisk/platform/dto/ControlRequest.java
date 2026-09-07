package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.ControlType;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.util.List;

public record ControlRequest(
        @NotNull String assetId,
        @NotBlank String name,
        String description,
        @NotNull ControlType controlType,
        @NotNull @DecimalMin("0.0") @DecimalMax("1.0") Double effectivenessScore,
        boolean implemented,
        BigDecimal annualCost,
        List<String> frameworkMappings
) {
}
