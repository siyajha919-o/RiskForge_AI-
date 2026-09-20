package com.cyberrisk.platform.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "assets")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Asset {

    @Id
    @GeneratedValue
    private UUID id;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AssetType assetType;

    private String businessUnit;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AssetCriticality criticality;

    /**
     * Annual business value (revenue, service value, or contractual value)
     * that depends on this asset remaining available, confidential and
     * intact. Used as the base for financial impact estimation.
     */
    @Column(nullable = false)
    private BigDecimal annualBusinessValue;

    /**
     * Approximate count of sensitive/regulated records held or processed by
     * this asset, if any. Drives data-breach cost estimation. Nullable.
     */
    private Long sensitiveRecordCount;

    @Builder.Default
    private Instant createdAt = Instant.now();

    @Builder.Default
    private Instant updatedAt = Instant.now();

    @PreUpdate
    public void touch() {
        this.updatedAt = Instant.now();
    }
}
