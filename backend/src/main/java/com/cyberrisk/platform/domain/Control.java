package com.cyberrisk.platform.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "controls")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Control {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "asset_id")
    private Asset asset;

    @Column(nullable = false)
    private String name;

    @Column(length = 1000)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ControlType controlType;

    /**
     * Fraction (0.0 - 1.0) of exploitation likelihood this control removes
     * when implemented, derived from telemetry such as configuration
     * strength, coverage, and incident history.
     */
    @Column(nullable = false)
    private Double effectivenessScore;

    /** Whether the control is currently live (true) or a proposed/candidate control (false). */
    @Builder.Default
    private boolean implemented = true;

    /** Estimated annual cost to implement/operate this control. */
    private BigDecimal annualCost;

    /** Free-text framework control references, e.g. "NIST CSF PR.AC-1", "ISO 27001 A.9.2". */
    @ElementCollection
    @CollectionTable(name = "control_framework_mappings", joinColumns = @JoinColumn(name = "control_id"))
    @Column(name = "mapping")
    @Builder.Default
    private List<String> frameworkMappings = new ArrayList<>();
}
