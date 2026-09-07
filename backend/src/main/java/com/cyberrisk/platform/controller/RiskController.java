package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.AssetRiskResponse;
import com.cyberrisk.platform.dto.OrganizationRiskResponse;
import com.cyberrisk.platform.dto.RiskSnapshotResponse;
import com.cyberrisk.platform.repository.RiskSnapshotRepository;
import com.cyberrisk.platform.service.RiskQuantificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/risk")
@RequiredArgsConstructor
public class RiskController {

    private final RiskQuantificationService riskQuantificationService;
    private final RiskSnapshotRepository riskSnapshotRepository;

    @GetMapping("/assets/{assetId}")
    public AssetRiskResponse assetRisk(@PathVariable String assetId) {
        return riskQuantificationService.calculateAssetRisk(assetId);
    }

    @GetMapping("/assets/{assetId}/history")
    public List<RiskSnapshotResponse> assetRiskHistory(
            @PathVariable String assetId) {

        return riskSnapshotRepository
                .findByAssetIdOrderByCalculatedAtDesc(assetId)
                .stream()
                .map(RiskSnapshotResponse::from)
                .collect(Collectors.toList());
    }

    @GetMapping("/organization")
    public OrganizationRiskResponse organizationRisk() {
        return riskQuantificationService.calculateOrganizationRisk();
    }
}