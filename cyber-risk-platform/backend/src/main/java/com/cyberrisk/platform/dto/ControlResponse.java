package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.Control;
import com.cyberrisk.platform.domain.ControlType;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public record ControlResponse(
        UUID id,
        UUID assetId,
        String name,
        String description,
        ControlType controlType,
        Double effectivenessScore,
        boolean implemented,
        BigDecimal annualCost,
        List<String> frameworkMappings
) {
    public static ControlResponse from(Control c) {
        return new ControlResponse(c.getId(), c.getAsset().getId(), c.getName(), c.getDescription(),
                c.getControlType(), c.getEffectivenessScore(), c.isImplemented(), c.getAnnualCost(),
                // Copy inside the transaction: getFrameworkMappings() is a lazy
                // PersistentBag, and handing it straight to the DTO defers loading
                // until Jackson serializes — by then the session is gone
                // (open-in-view is off), which surfaced as a bogus 401.
                new ArrayList<>(c.getFrameworkMappings()));
    }
}
