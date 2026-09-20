package com.cyberrisk.platform.dto;

import com.cyberrisk.platform.domain.Asset;
import com.cyberrisk.platform.domain.AssetCriticality;
import com.cyberrisk.platform.domain.AssetType;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record AssetResponse(
        UUID id,
        String name,
        AssetType assetType,
        String businessUnit,
        AssetCriticality criticality,
        BigDecimal annualBusinessValue,
        Long sensitiveRecordCount,
        Instant createdAt,
        Instant updatedAt
) {
    public static AssetResponse from(Asset a) {
        return new AssetResponse(a.getId(), a.getName(), a.getAssetType(), a.getBusinessUnit(),
                a.getCriticality(), a.getAnnualBusinessValue(), a.getSensitiveRecordCount(),
                a.getCreatedAt(), a.getUpdatedAt());
    }
}
