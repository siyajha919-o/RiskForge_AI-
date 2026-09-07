package com.cyberrisk.platform.service;

import com.cyberrisk.platform.domain.Asset;
import com.cyberrisk.platform.domain.AssetCriticality;
import com.cyberrisk.platform.domain.Control;
import com.cyberrisk.platform.domain.RiskSnapshot;
import com.cyberrisk.platform.domain.Vulnerability;
import com.cyberrisk.platform.domain.VulnerabilityStatus;
import com.cyberrisk.platform.dto.AssetRiskResponse;
import com.cyberrisk.platform.dto.FindingContribution;
import com.cyberrisk.platform.dto.OrganizationRiskResponse;
import com.cyberrisk.platform.repository.AssetRepository;
import com.cyberrisk.platform.repository.ControlRepository;
import com.cyberrisk.platform.repository.RiskSnapshotRepository;
import com.cyberrisk.platform.repository.VulnerabilityRepository;

import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RiskQuantificationService {

    private final AssetRepository assetRepository;
    private final VulnerabilityRepository vulnerabilityRepository;
    private final ControlRepository controlRepository;
    private final RiskSnapshotRepository riskSnapshotRepository;
    private final MonteCarloRiskSimulator simulator;

    @Transactional
    public AssetRiskResponse calculateAssetRisk(String assetId) {

        Asset asset = assetRepository.findById(assetId)
                .orElseThrow(() ->
                        new EntityNotFoundException("Asset not found: " + assetId)
                );

        List<Vulnerability> openFindings =
                vulnerabilityRepository.findByAssetIdAndStatus(
                        assetId,
                        VulnerabilityStatus.OPEN
                );

        List<Control> controls =
                controlRepository.findByAssetIdAndImplementedTrue(assetId);

        double combinedControlEffectiveness =
                combinedEffectiveness(controls);

        List<FindingContribution> contributions = new ArrayList<>();
        List<Double> likelihoods = new ArrayList<>();
        List<Double> impacts = new ArrayList<>();

        double totalEal = 0.0;
        double totalAro = 0.0;

        for (Vulnerability vulnerability : openFindings) {

            double baseLikelihood;

            if (vulnerability.getExploitabilityScore() != null) {
                baseLikelihood =
                        vulnerability.getExploitabilityScore();
            } else {
                baseLikelihood =
                        RiskModelConstants.baseAnnualProbability(
                                vulnerability.getCvssScore()
                        );
            }

            double adjustedLikelihood =
                    RiskModelConstants.clamp(
                            baseLikelihood
                                    * (1.0 - combinedControlEffectiveness),
                            0.0,
                            1.0
                    );

            double impact =
                    estimateImpact(
                            asset,
                            vulnerability.getCvssScore()
                    );

            double contribution =
                    adjustedLikelihood * impact;

            likelihoods.add(adjustedLikelihood);
            impacts.add(impact);

            totalEal += contribution;
            totalAro += adjustedLikelihood;

            contributions.add(
                    new FindingContribution(
                            vulnerability.getId(),
                            vulnerability.getTitle(),
                            vulnerability.getCveId(),
                            vulnerability.getCvssScore(),
                            bd(adjustedLikelihood),
                            bd(impact),
                            bd(contribution)
                    )
            );
        }

        double valueAtRisk95 =
                simulator.simulateValueAtRisk(
                        likelihoods,
                        impacts
                );

        double sle =
                totalAro > 0.0
                        ? totalEal / totalAro
                        : 0.0;

        List<FindingContribution> topContributors =
                contributions.stream()
                        .sorted(
                                Comparator.comparing(
                                        FindingContribution::contributionToExpectedAnnualLoss
                                ).reversed()
                        )
                        .limit(10)
                        .collect(Collectors.toList());

        RiskSnapshot snapshot =
                RiskSnapshot.builder()
                        .asset(asset)
                        .annualizedRateOfOccurrence(
                                bd(totalAro)
                        )
                        .singleLossExpectancy(
                                bd(sle)
                        )
                        .expectedAnnualLoss(
                                bd(totalEal)
                        )
                        .valueAtRisk95(
                                bd(valueAtRisk95)
                        )
                        .openFindingsCount(
                                openFindings.size()
                        )
                        .build();

        riskSnapshotRepository.save(snapshot);

        return new AssetRiskResponse(
                asset.getId(),
                asset.getName(),
                asset.getBusinessUnit(),
                toAssetCriticality(asset.getCriticality()),
                openFindings.size(),
                bd(totalAro),
                bd(sle),
                bd(totalEal),
                bd(valueAtRisk95),
                topContributors
        );
    }

    @Transactional
    public OrganizationRiskResponse calculateOrganizationRisk() {

        List<Asset> assets =
                assetRepository.findAll();

        List<AssetRiskResponse> assetRisks =
                assets.stream()
                        .map(asset ->
                                calculateAssetRisk(
                                        asset.getId()
                                )
                        )
                        .collect(Collectors.toList());

        BigDecimal totalEal =
                assetRisks.stream()
                        .map(
                                AssetRiskResponse::expectedAnnualLoss
                        )
                        .reduce(
                                BigDecimal.ZERO,
                                BigDecimal::add
                        );

        BigDecimal totalVar =
                assetRisks.stream()
                        .map(
                                AssetRiskResponse::valueAtRisk95
                        )
                        .reduce(
                                BigDecimal.ZERO,
                                BigDecimal::add
                        );

        Map<String, BigDecimal> byBusinessUnit =
                assetRisks.stream()
                        .collect(
                                Collectors.groupingBy(
                                        risk ->
                                                risk.businessUnit() == null
                                                        ? "Unassigned"
                                                        : risk.businessUnit(),
                                        Collectors.reducing(
                                                BigDecimal.ZERO,
                                                AssetRiskResponse::expectedAnnualLoss,
                                                BigDecimal::add
                                        )
                                )
                        );

        List<AssetRiskResponse> topRiskyAssets =
                assetRisks.stream()
                        .sorted(
                                Comparator.comparing(
                                        AssetRiskResponse::expectedAnnualLoss
                                ).reversed()
                        )
                        .limit(10)
                        .collect(Collectors.toList());

        return new OrganizationRiskResponse(
                assets.size(),
                totalEal,
                totalVar,
                byBusinessUnit,
                topRiskyAssets
        );
    }

    private double combinedEffectiveness(
            List<Control> controls
    ) {

        double survivalProbability = 1.0;

        for (Control control : controls) {

            double effectiveness =
                    RiskModelConstants.clamp(
                            control.getEffectivenessScore(),
                            0.0,
                            1.0
                    );

            survivalProbability *=
                    (1.0 - effectiveness);
        }

        return RiskModelConstants.clamp(
                1.0 - survivalProbability,
                0.0,
                0.98
        );
    }

    private double estimateImpact(
            Asset asset,
            double cvssScore
    ) {

        double severityFactor =
                RiskModelConstants
                        .severityImpactFactor(
                                cvssScore
                        );

        double businessValueImpact = 0.0;

        if (asset.getAnnualBusinessValue() != null) {

            AssetCriticality criticality =
                    toAssetCriticality(
                            asset.getCriticality()
                    );

            double criticalityWeight =
                    criticality != null
                            ? criticality.getWeight()
                            : 1.0;

            businessValueImpact =
                    asset.getAnnualBusinessValue()
                            .doubleValue()
                            * criticalityWeight
                            * severityFactor;
        }

        double breachCost = 0.0;

        if (asset.getSensitiveRecordCount() != null
                && asset.getSensitiveRecordCount() > 0) {

            breachCost =
                    asset.getSensitiveRecordCount()
                            * RiskModelConstants.COST_PER_RECORD
                            * (cvssScore / 10.0);
        }

        return businessValueImpact + breachCost;
    }

    private AssetCriticality toAssetCriticality(
            String value
    ) {

        if (value == null || value.isBlank()) {
            return null;
        }

        String normalized =
                value.trim()
                        .toUpperCase()
                        .replace(" ", "_")
                        .replace("-", "_");

        try {
            return AssetCriticality.valueOf(
                    normalized
            );
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static BigDecimal bd(
            double value
    ) {

        return BigDecimal.valueOf(value)
                .setScale(
                        2,
                        RoundingMode.HALF_UP
                );
    }
}