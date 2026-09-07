package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.Asset;

import java.math.BigDecimal;
import java.time.Instant;

public record AssetResponse(
        String id,
        String name,
        String assetType,
        String businessUnit,
        String criticality,
        BigDecimal annualBusinessValue,
        Long sensitiveRecordCount,
        Instant createdAt,
        Instant updatedAt
) {
    public static AssetResponse from(Asset a) {
        return new AssetResponse(
                a.getId(),
                a.getName(),
                a.getAssetType(),
                a.getBusinessUnit(),
                a.getCriticality(),
                a.getAnnualBusinessValue(),
                a.getSensitiveRecordCount(),
                a.getCreatedAt(),
                a.getUpdatedAt()
        );
    }
}