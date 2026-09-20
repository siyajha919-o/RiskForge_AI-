package com.cyberrisk.platform.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Landing route so opening the gateway in a browser explains itself instead of
 * returning a bare 404 — the dashboard runs as a separate Vite service.
 */
@RestController
public class RootController {

    @GetMapping("/")
    public Map<String, String> root() {
        return Map.of(
                "service", "RiskForge API gateway",
                "note", "This is the JSON API, not the dashboard UI.",
                "dashboardUi", "http://localhost:5173",
                "health", "/actuator/health"
        );
    }
}
