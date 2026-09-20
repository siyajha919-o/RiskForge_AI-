package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.client.RiskEngineClient;
import com.cyberrisk.platform.client.RiskEngineUnavailableException;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Exposes the Python risk engine through the Java API so clients have a single
 * origin and, once security is applied, a single authentication surface.
 */
@RestController
@RequestMapping("/api/v1/platform/riskengine")
@RequiredArgsConstructor
public class RiskEngineProxyController {

    private final RiskEngineClient client;

    @ExceptionHandler(RiskEngineUnavailableException.class)
    public ResponseEntity<Map<String, Object>> handleUnavailable(RiskEngineUnavailableException ex) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("success", false, "data", "", "message", ex.getMessage()));
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/dashboard")
    public Map<String, Object> dashboard() {
        return client.getDashboard();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/dashboard/{section}")
    public Object dashboardSection(@PathVariable String section) {
        return client.getDashboardSection(section);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/business-units")
    public List<Map<String, Object>> businessUnits() {
        return client.getBusinessUnits();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/organizations")
    public List<Map<String, Object>> organizations() {
        return client.getOrganizations();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/compliance/report")
    public Map<String, Object> complianceReport() {
        return client.getComplianceReport();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/scenarios")
    public List<Map<String, Object>> scenarios() {
        return client.getScenarios();
    }

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping("/scenarios/simulate")
    public Map<String, Object> simulateScenario(@RequestBody Map<String, Object> request) {
        return client.simulateScenario(request);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/attack-paths")
    public Map<String, Object> attackPaths() {
        return client.getAttackPaths();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @PostMapping("/ask")
    public Map<String, Object> ask(@RequestBody Map<String, Object> request) {
        return client.ask(request);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/recommendations")
    public Map<String, Object> recommendations() {
        return client.getRecommendations();
    }

    @PreAuthorize("hasAnyRole('CISO','ADMIN')")
    @PostMapping("/recompute")
    public Map<String, Object> recompute(@RequestParam(defaultValue = "incremental") String mode,
                                         @RequestParam(defaultValue = "false") boolean force) {
        return client.triggerRecompute(mode, force);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/recompute/status")
    public Map<String, Object> recomputeStatus() {
        return client.getRecomputeStatus();
    }
}
