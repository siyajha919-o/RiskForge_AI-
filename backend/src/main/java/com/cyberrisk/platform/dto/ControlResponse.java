package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.Control;
import com.cyberrisk.platform.domain.ControlType;

import java.math.BigDecimal;
import java.util.List;

public record ControlResponse(
        String id,
        String assetId,
        String name,
        String description,
        ControlType controlType,
        Double effectivenessScore,
        boolean implemented,
        BigDecimal annualCost,
        List<String> frameworkMappings
) {

    public static ControlResponse from(Control c) {
        return new ControlResponse(
                c.getId().toString(),
                c.getAsset().getId().toString(),
                c.getName(),
                c.getDescription(),
                c.getControlType(),
                c.getEffectivenessScore(),
                c.isImplemented(),
                c.getAnnualCost(),
                c.getFrameworkMappings()
        );
    }
}