package com.cyberrisk.platform.service;

import com.cyberrisk.platform.domain.*;
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
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Core Risk Quantification Engine: turns technical findings + asset
 * criticality + control effectiveness into financial exposure metrics
 * (Expected Annual Loss and Value at Risk), at asset and organization level.
 */
@Service
@RequiredArgsConstructor
public class RiskQuantificationService {

    private final AssetRepository assetRepository;
    private final VulnerabilityRepository vulnerabilityRepository;
    private final ControlRepository controlRepository;
    private final RiskSnapshotRepository riskSnapshotRepository;
    private final MonteCarloRiskSimulator simulator;

    /**
     * Computes an asset's risk without persisting anything. This is what the
     * read endpoints use: recording a snapshot on every GET turned the trend
     * history into a log of dashboard page views rather than of risk changes.
     */
    @Transactional(readOnly = true)
    public AssetRiskResponse calculateAssetRisk(UUID assetId) {
        Asset asset = assetRepository.findById(assetId)
                .orElseThrow(() -> new EntityNotFoundException("Asset not found: " + assetId));

        List<Vulnerability> openFindings = vulnerabilityRepository
                .findByAssetIdAndStatus(assetId, VulnerabilityStatus.OPEN);
        List<Control> controls = controlRepository.findByAssetIdAndImplementedTrue(assetId);

        double combinedControlEffectiveness = combinedEffectiveness(controls);

        List<FindingContribution> contributions = new ArrayList<>();
        List<Double> likelihoods = new ArrayList<>();
        List<Double> impacts = new ArrayList<>();
        double totalEal = 0.0;
        double totalAro = 0.0;

        for (Vulnerability v : openFindings) {
            double baseLikelihood = v.getExploitabilityScore() != null
                    ? v.getExploitabilityScore()
                    : RiskModelConstants.baseAnnualProbability(v.getCvssScore());
            double adjustedLikelihood = RiskModelConstants.clamp(
                    baseLikelihood * (1 - combinedControlEffectiveness), 0.0, 1.0);

            double impact = estimateImpact(asset, v.getCvssScore());
            double contribution = adjustedLikelihood * impact;

            likelihoods.add(adjustedLikelihood);
            impacts.add(impact);
            totalEal += contribution;
            totalAro += adjustedLikelihood;

            contributions.add(new FindingContribution(
                    v.getId(), v.getTitle(), v.getCveId(), v.getCvssScore(),
                    bd(adjustedLikelihood), bd(impact), bd(contribution)));
        }

        double valueAtRisk95 = simulator.simulateValueAtRisk(likelihoods, impacts);
        double sle = totalAro > 0 ? totalEal / totalAro : 0.0;

        List<FindingContribution> topContributors = contributions.stream()
                .sorted(Comparator.comparing(FindingContribution::contributionToExpectedAnnualLoss).reversed())
                .limit(10)
                .collect(Collectors.toList());

        return new AssetRiskResponse(
                asset.getId(), asset.getName(), asset.getBusinessUnit(), asset.getCriticality(),
                openFindings.size(), bd(totalAro), bd(sle), bd(totalEal), bd(valueAtRisk95), topContributors);
    }

    /**
     * Computes an asset's risk and records it as a point in the trend history.
     * Deliberately a separate, write-flavoured operation so that history grows
     * only when someone (or a scheduled job) asks for a measurement to be kept.
     */
    @Transactional
    public AssetRiskResponse recordAssetRiskSnapshot(UUID assetId) {
        AssetRiskResponse risk = calculateAssetRisk(assetId);
        Asset asset = assetRepository.getReferenceById(assetId);

        riskSnapshotRepository.save(RiskSnapshot.builder()
                .asset(asset)
                .annualizedRateOfOccurrence(risk.annualizedRateOfOccurrence())
                .singleLossExpectancy(risk.singleLossExpectancy())
                .expectedAnnualLoss(risk.expectedAnnualLoss())
                .valueAtRisk95(risk.valueAtRisk95())
                .openFindingsCount(risk.openFindingsCount())
                .build());

        return risk;
    }

    /** Records a snapshot for every asset — one trend point per asset per run. */
    @Transactional
    public List<AssetRiskResponse> recordOrganizationRiskSnapshots() {
        return assetRepository.findAll().stream()
                .map(a -> recordAssetRiskSnapshot(a.getId()))
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public OrganizationRiskResponse calculateOrganizationRisk() {
        List<Asset> assets = assetRepository.findAll();

        List<AssetRiskResponse> assetRisks = assets.stream()
                .map(a -> calculateAssetRisk(a.getId()))
                .collect(Collectors.toList());

        BigDecimal totalEal = assetRisks.stream()
                .map(AssetRiskResponse::expectedAnnualLoss)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        BigDecimal totalVar = assetRisks.stream()
                .map(AssetRiskResponse::valueAtRisk95)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        Map<String, BigDecimal> byBusinessUnit = assetRisks.stream()
                .collect(Collectors.groupingBy(
                        r -> r.businessUnit() == null ? "Unassigned" : r.businessUnit(),
                        Collectors.reducing(BigDecimal.ZERO, AssetRiskResponse::expectedAnnualLoss, BigDecimal::add)));

        List<AssetRiskResponse> topRiskyAssets = assetRisks.stream()
                .sorted(Comparator.comparing(AssetRiskResponse::expectedAnnualLoss).reversed())
                .limit(10)
                .collect(Collectors.toList());

        return new OrganizationRiskResponse(assets.size(), totalEal, totalVar, byBusinessUnit, topRiskyAssets);
    }

    /** Combined risk reduction from all implemented controls, assuming independence: 1 - product(1 - e_i). */
    private double combinedEffectiveness(List<Control> controls) {
        double survivalProbability = 1.0;
        for (Control c : controls) {
            survivalProbability *= (1 - RiskModelConstants.clamp(c.getEffectivenessScore(), 0.0, 1.0));
        }
        return RiskModelConstants.clamp(1 - survivalProbability, 0.0, 0.98);
    }

    private double estimateImpact(Asset asset, double cvssScore) {
        double severityFactor = RiskModelConstants.severityImpactFactor(cvssScore);
        double businessValueImpact = asset.getAnnualBusinessValue().doubleValue()
                * asset.getCriticality().getWeight() * severityFactor;

        double breachCost = 0.0;
        if (asset.getSensitiveRecordCount() != null && asset.getSensitiveRecordCount() > 0) {
            breachCost = asset.getSensitiveRecordCount() * RiskModelConstants.COST_PER_RECORD
                    * (cvssScore / 10.0);
        }
        return businessValueImpact + breachCost;
    }

    private static BigDecimal bd(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP);
    }
}
