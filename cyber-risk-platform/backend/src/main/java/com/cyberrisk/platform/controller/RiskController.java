package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.AssetRiskResponse;
import com.cyberrisk.platform.dto.OrganizationRiskResponse;
import com.cyberrisk.platform.dto.RiskSnapshotResponse;
import com.cyberrisk.platform.repository.RiskSnapshotRepository;
import com.cyberrisk.platform.service.RiskQuantificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/v1/platform/risk")
@RequiredArgsConstructor
public class RiskController {

    private final RiskQuantificationService riskQuantificationService;
    private final RiskSnapshotRepository riskSnapshotRepository;

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/assets/{assetId}")
    public AssetRiskResponse assetRisk(@PathVariable UUID assetId) {
        return riskQuantificationService.calculateAssetRisk(assetId);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/assets/{assetId}/history")
    public List<RiskSnapshotResponse> assetRiskHistory(@PathVariable UUID assetId) {
        return riskSnapshotRepository.findByAssetIdOrderByCalculatedAtDesc(assetId).stream()
                .map(RiskSnapshotResponse::from).collect(Collectors.toList());
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/organization")
    public OrganizationRiskResponse organizationRisk() {
        return riskQuantificationService.calculateOrganizationRisk();
    }

    /**
     * Records a trend point. Reading risk no longer writes history, so taking a
     * measurement is now an explicit action rather than a side effect of a GET.
     */
    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping("/assets/{assetId}/snapshots")
    @ResponseStatus(HttpStatus.CREATED)
    public AssetRiskResponse recordAssetSnapshot(@PathVariable UUID assetId) {
        return riskQuantificationService.recordAssetRiskSnapshot(assetId);
    }

    @PreAuthorize("hasAnyRole('CISO','ADMIN')")
    @PostMapping("/snapshots")
    @ResponseStatus(HttpStatus.CREATED)
    public List<AssetRiskResponse> recordOrganizationSnapshots() {
        return riskQuantificationService.recordOrganizationRiskSnapshots();
    }
}
