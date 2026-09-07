package com.cyberrisk.platform.domain;

import jakarta.persistence.*;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
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

    // 1. asset_id
    @Id
    @Column(name = "asset_id")
    private String id;

    // 2. organization_id
    @Column(name = "organization_id")
    private String organizationId;

    // 3. business_unit_id
    @Column(name = "business_unit_id")
    private String businessUnit;

    // 4. asset_name
    @Column(name = "asset_name")
    private String name;

    // 5. asset_type
    @Column(name = "asset_type")
    private String assetType;

    // 6. operating_system
    @Column(name = "operating_system")
    private String operatingSystem;

    // 7. environment
    @Column(name = "environment")
    private String environment;

    // 8. cloud_provider
    @Column(name = "cloud_provider")
    private String cloudProvider;

    // 9. region
    @Column(name = "region")
    private String region;

    // 10. internet_exposed
    @Column(name = "internet_exposed")
    private Boolean internetExposed;

    // 11. asset_owner
    @Column(name = "asset_owner")
    private String assetOwner;

    // 12. business_service
    @Column(name = "business_service")
    private String businessService;

    // 13. data_classification
    @Column(name = "data_classification")
    private String dataClassification;

    // 14. asset_criticality
    @Column(name = "asset_criticality")
    private String criticality;

    // 15. confidentiality_score
    @Column(name = "confidentiality_score")
    private Integer confidentialityScore;

    // 16. integrity_score
    @Column(name = "integrity_score")
    private Integer integrityScore;

    // 17. availability_score
    @Column(name = "availability_score")
    private Integer availabilityScore;

    // 18. revenue_dependency
    @Column(name = "revenue_dependency")
    private BigDecimal revenueDependency;

    // 19. customer_dependency
    @Column(name = "customer_dependency")
    private BigDecimal customerDependency;

    // 20. regulatory_dependency
    @Column(name = "regulatory_dependency")
    private BigDecimal regulatoryDependency;

    // 21. dependency_count
    @Column(name = "dependency_count")
    private Integer dependencyCount;

    // 22. asset_age_days
    @Column(name = "asset_age_days")
    private Integer assetAgeDays;

    // 23. current_risk_score
    @Column(name = "current_risk_score")
    private BigDecimal currentRiskScore;


    /*
     * OLD BACKEND FIELDS
     *
     * These columns do NOT exist in your PostgreSQL assets table.
     * @Transient prevents Hibernate from searching for them in PostgreSQL,
     * while allowing the existing backend code to continue using them.
     */

    @Transient
    private BigDecimal annualBusinessValue;

    @Transient
    private Long sensitiveRecordCount;

    @Transient
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Transient
    @Builder.Default
    private Instant updatedAt = Instant.now();


    /*
     * Your PostgreSQL asset_id is VARCHAR, not UUID.
     * This creates an ID automatically when the backend creates a new asset.
     */
    @PrePersist
    public void generateId() {
        if (id == null || id.isBlank()) {
            id = UUID.randomUUID().toString();
        }
    }

    @PreUpdate
    public void touch() {
        this.updatedAt = Instant.now();
    }
}