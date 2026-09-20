package com.cyberrisk.platform.client;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

/**
 * Talks to the Python RiskEngine, which owns the actual FAIR/Monte-Carlo model.
 *
 * The Java side deliberately does not recompute risk: keeping two independent
 * implementations of the same financial model is how they drift apart.
 */
@Slf4j
@Component
public class RiskEngineClient {

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() {};
    private static final ParameterizedTypeReference<List<Map<String, Object>>> LIST_TYPE =
            new ParameterizedTypeReference<>() {};

    private final RestTemplate restTemplate;
    private final String baseUrl;
    private final String sharedSecret;
    private final String username;
    private final String password;

    /** Cached engine token. The engine issues short-lived JWTs, so we re-login on 401. */
    private volatile String engineToken;

    public RiskEngineClient(RestTemplate riskEngineRestTemplate,
                            @Value("${risk-engine.url}") String baseUrl,
                            @Value("${risk-engine.shared-secret:}") String sharedSecret,
                            @Value("${risk-engine.username:}") String username,
                            @Value("${risk-engine.password:}") String password) {
        this.restTemplate = riskEngineRestTemplate;
        this.baseUrl = baseUrl;
        this.sharedSecret = sharedSecret;
        this.username = username;
        this.password = password;
    }

    /**
     * The engine authenticates callers with the same bearer tokens it issues to
     * the dashboard; there is no separate service-account mechanism. We hold one
     * token and refresh it when the engine rejects it.
     */
    private synchronized String login() {
        if (username == null || username.isBlank()) {
            return null;
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        Map<String, Object> body = Map.of("email", username, "password", password);
        try {
            Map<String, Object> res = restTemplate.exchange(
                    baseUrl + "/api/v1/auth/login", HttpMethod.POST,
                    new HttpEntity<>(body, headers), MAP_TYPE).getBody();
            engineToken = res == null ? null : (String) res.get("access_token");
            return engineToken;
        } catch (ResourceAccessException ex) {
            throw new RiskEngineUnavailableException("Risk engine is unreachable.", ex);
        } catch (RestClientResponseException ex) {
            log.error("RiskEngine rejected the service credentials: {}", ex.getStatusCode());
            throw new RiskEngineUnavailableException(
                    "Risk engine rejected the configured service credentials.", ex);
        }
    }

    private String token() {
        String t = engineToken;
        return t != null ? t : login();
    }

    private HttpHeaders headers(boolean withBody) {
        HttpHeaders headers = new HttpHeaders();
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        if (withBody) {
            headers.setContentType(MediaType.APPLICATION_JSON);
        }
        if (sharedSecret != null && !sharedSecret.isBlank()) {
            headers.set("X-Internal-Secret", sharedSecret);
        }
        String t = token();
        if (t != null) {
            headers.setBearerAuth(t);
        }
        return headers;
    }

    private HttpEntity<Void> authEntity() {
        return new HttpEntity<>(headers(false));
    }

    private HttpEntity<Object> authEntity(Object body) {
        return new HttpEntity<>(body, headers(true));
    }

    private <T> T exchange(String path, HttpMethod method, HttpEntity<?> entity,
                           ParameterizedTypeReference<T> type) {
        return exchange(path, method, entity, type, true);
    }

    private <T> T exchange(String path, HttpMethod method, HttpEntity<?> entity,
                           ParameterizedTypeReference<T> type, boolean retryOnAuthFailure) {
        String url = baseUrl + path;
        try {
            return restTemplate.exchange(url, method, entity, type).getBody();
        } catch (ResourceAccessException ex) {
            // Connection refused / timed out — the engine is down or still computing.
            log.error("RiskEngine unreachable at {}: {}", url, ex.getMessage());
            throw new RiskEngineUnavailableException("Risk engine is unreachable.", ex);
        } catch (RestClientResponseException ex) {
            // A cached token that has expired looks exactly like a bad one; take
            // one fresh token and retry before declaring the engine unavailable.
            if (ex.getStatusCode().value() == 401 && retryOnAuthFailure) {
                engineToken = null;
                if (login() != null) {
                    HttpEntity<?> retry = entity.hasBody()
                            ? new HttpEntity<>(entity.getBody(), headers(true))
                            : new HttpEntity<>(headers(false));
                    return exchange(path, method, retry, type, false);
                }
            }
            log.error("RiskEngine returned {} for {}", ex.getStatusCode(), url);
            throw new RiskEngineUnavailableException(
                    "Risk engine returned " + ex.getStatusCode() + ".", ex);
        }
    }

    public Map<String, Object> getDashboard() {
        return exchange("/api/v1/dashboard", HttpMethod.GET, authEntity(), MAP_TYPE);
    }

    public Object getDashboardSection(String section) {
        return exchange("/api/v1/dashboard/" + section, HttpMethod.GET, authEntity(),
                new ParameterizedTypeReference<Object>() {});
    }

    public List<Map<String, Object>> getBusinessUnits() {
        return exchange("/api/v1/risk/business-units", HttpMethod.GET, authEntity(), LIST_TYPE);
    }

    public List<Map<String, Object>> getOrganizations() {
        return exchange("/api/v1/risk/organizations", HttpMethod.GET, authEntity(), LIST_TYPE);
    }

    public Map<String, Object> getComplianceReport() {
        return exchange("/api/v1/compliance", HttpMethod.GET, authEntity(), MAP_TYPE);
    }

    public List<Map<String, Object>> getScenarios() {
        return exchange("/api/v1/scenarios/precomputed", HttpMethod.GET, authEntity(), LIST_TYPE);
    }

    public Map<String, Object> simulateScenario(Map<String, Object> request) {
        return exchange("/api/v1/scenarios/simulate", HttpMethod.POST, authEntity(request), MAP_TYPE);
    }

    public Map<String, Object> getAttackPaths() {
        return exchange("/api/v1/network", HttpMethod.GET, authEntity(), MAP_TYPE);
    }

    public Map<String, Object> ask(Map<String, Object> request) {
        return exchange("/api/v1/ask", HttpMethod.POST, authEntity(request), MAP_TYPE);
    }

    public Map<String, Object> getRecommendations() {
        return exchange("/api/v1/recommendations", HttpMethod.GET, authEntity(), MAP_TYPE);
    }

    public Map<String, Object> triggerRecompute(String mode, boolean force) {
        String path = "/api/v1/pipeline/recompute?mode=" + mode + "&force=" + force;
        return exchange(path, HttpMethod.POST, authEntity(null), MAP_TYPE);
    }

    public Map<String, Object> getRecomputeStatus() {
        return exchange("/api/v1/pipeline/status", HttpMethod.GET, authEntity(), MAP_TYPE);
    }
}
