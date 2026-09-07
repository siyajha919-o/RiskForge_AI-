package com.cyberrisk.platform;

import com.cyberrisk.platform.domain.*;
import com.cyberrisk.platform.dto.AssetRiskResponse;
import com.cyberrisk.platform.repository.AssetRepository;
import com.cyberrisk.platform.repository.ControlRepository;
import com.cyberrisk.platform.repository.VulnerabilityRepository;
import com.cyberrisk.platform.service.RiskQuantificationService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("demo")
class RiskQuantificationServiceTest {

    @Autowired
    private AssetRepository assetRepository;
    @Autowired
    private VulnerabilityRepository vulnerabilityRepository;
    @Autowired
    private ControlRepository controlRepository;
    @Autowired
    private RiskQuantificationService riskQuantificationService;

    @Test
    void expectedAnnualLossIncreasesWithSeverityAndDropsWithControls() {
        Asset asset = assetRepository.save(Asset.builder()
                .name("Test Asset")
                .assetType(AssetType.SERVER)
                .businessUnit("QA")
                .criticality(AssetCriticality.HIGH)
                .annualBusinessValue(BigDecimal.valueOf(1_000_000))
                .sensitiveRecordCount(0L)
                .build());

        vulnerabilityRepository.save(Vulnerability.builder()
                .asset(asset).title("Critical unpatched vuln").cvssScore(9.5)
                .status(VulnerabilityStatus.OPEN).source(VulnerabilitySource.VULNERABILITY_SCANNER).build());

        AssetRiskResponse withoutControls = riskQuantificationService.calculateAssetRisk(asset.getId());
        assertThat(withoutControls.expectedAnnualLoss()).isGreaterThan(BigDecimal.ZERO);

        controlRepository.save(Control.builder()
                .asset(asset).name("EDR").controlType(ControlType.PREVENTIVE)
                .effectivenessScore(0.8).implemented(true).build());

        AssetRiskResponse withControls = riskQuantificationService.calculateAssetRisk(asset.getId());
        assertThat(withControls.expectedAnnualLoss()).isLessThan(withoutControls.expectedAnnualLoss());
    }
}
