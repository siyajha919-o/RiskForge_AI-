package com.cyberrisk.platform.config;

import com.cyberrisk.platform.domain.*;
import com.cyberrisk.platform.repository.AssetRepository;
import com.cyberrisk.platform.repository.ControlRepository;
import com.cyberrisk.platform.repository.VulnerabilityRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;

/** Seeds representative assets, findings, and controls so the API is explorable out of the box. */
@Component
@Profile("demo")
@RequiredArgsConstructor
public class DemoDataSeeder implements CommandLineRunner {

    private final AssetRepository assetRepository;
    private final VulnerabilityRepository vulnerabilityRepository;
    private final ControlRepository controlRepository;

    @Override
    public void run(String... args) {
        if (assetRepository.count() > 0) {
            return;
        }

        Asset paymentsApi = assetRepository.save(Asset.builder()
                .name("Payments API")
                .assetType(AssetType.APPLICATION)
                .businessUnit("Payments")
                .criticality(AssetCriticality.CRITICAL)
                .annualBusinessValue(BigDecimal.valueOf(50_000_000))
                .sensitiveRecordCount(2_000_000L)
                .build());

        Asset customerDb = assetRepository.save(Asset.builder()
                .name("Customer Records Database")
                .assetType(AssetType.DATABASE)
                .businessUnit("Retail Banking")
                .criticality(AssetCriticality.CRITICAL)
                .annualBusinessValue(BigDecimal.valueOf(30_000_000))
                .sensitiveRecordCount(5_000_000L)
                .build());

        Asset internalWiki = assetRepository.save(Asset.builder()
                .name("Internal Wiki")
                .assetType(AssetType.APPLICATION)
                .businessUnit("Corporate IT")
                .criticality(AssetCriticality.LOW)
                .annualBusinessValue(BigDecimal.valueOf(500_000))
                .sensitiveRecordCount(0L)
                .build());

        vulnerabilityRepository.saveAll(List.of(
                Vulnerability.builder().asset(paymentsApi).cveId("CVE-2024-1111")
                        .title("Unauthenticated remote code execution in payment gateway library")
                        .cvssScore(9.8).exploitabilityScore(0.4)
                        .status(VulnerabilityStatus.OPEN).source(VulnerabilitySource.VULNERABILITY_SCANNER).build(),
                Vulnerability.builder().asset(paymentsApi).cveId("CVE-2024-2222")
                        .title("Broken access control on internal admin endpoint")
                        .cvssScore(8.1)
                        .status(VulnerabilityStatus.OPEN).source(VulnerabilitySource.SIEM).build(),
                Vulnerability.builder().asset(customerDb).cveId("CVE-2023-3333")
                        .title("Excessive IAM privileges on database service account")
                        .cvssScore(7.5)
                        .status(VulnerabilityStatus.OPEN).source(VulnerabilitySource.IAM).build(),
                Vulnerability.builder().asset(internalWiki).cveId("CVE-2022-4444")
                        .title("Outdated TLS configuration")
                        .cvssScore(4.3)
                        .status(VulnerabilityStatus.OPEN).source(VulnerabilitySource.CSPM).build()
        ));

        controlRepository.saveAll(List.of(
                Control.builder().asset(paymentsApi).name("Web Application Firewall")
                        .controlType(ControlType.PREVENTIVE).effectivenessScore(0.5).implemented(true)
                        .annualCost(BigDecimal.valueOf(120_000))
                        .frameworkMappings(List.of("NIST CSF PR.PT-3", "CIS Control 13")).build(),
                Control.builder().asset(paymentsApi).name("24x7 SOC Monitoring")
                        .controlType(ControlType.DETECTIVE).effectivenessScore(0.3).implemented(true)
                        .annualCost(BigDecimal.valueOf(300_000))
                        .frameworkMappings(List.of("NIST CSF DE.CM-1")).build(),
                Control.builder().asset(customerDb).name("Privileged Access Management")
                        .controlType(ControlType.PREVENTIVE).effectivenessScore(0.6).implemented(false)
                        .annualCost(BigDecimal.valueOf(180_000))
                        .frameworkMappings(List.of("NIST CSF PR.AC-4", "ISO 27001 A.9.2")).build()
        ));
    }
}
