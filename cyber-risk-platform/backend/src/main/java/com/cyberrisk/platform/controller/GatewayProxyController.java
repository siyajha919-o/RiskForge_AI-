package com.cyberrisk.platform.controller;

import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;

/**
 * Transparent passthrough to the Python risk engine.
 *
 * Everything under /api/v1 that no other controller claims is relayed to the
 * engine unchanged — same method, path, query string and body — so the gateway
 * is a single origin for the dashboard without the Java side having to restate
 * each of the engine's ~30 endpoint signatures. New engine routes work here the
 * day they are added, with no change on this side.
 *
 * <p><b>Identity.</b> The caller's own bearer token is forwarded verbatim and
 * the engine validates it: the engine owns the user store, so it, not this
 * gateway, decides who the caller is on proxied routes. This class therefore
 * performs no authorization of its own, and the matching Spring Security rule
 * permits these paths. The platform's own resources under /api/v1/platform are
 * a separate surface and stay authenticated by this service.
 *
 * <p>Spring MVC resolves the most specific mapping first, so the explicitly
 * mapped controllers always win over the /** pattern here.
 */
@Slf4j
@RestController
public class GatewayProxyController {

    /**
     * Hop-by-hop and length headers are dropped: they describe the connection
     * this gateway received, not the one it opens, and relaying a stale
     * Content-Length or an inherited Transfer-Encoding corrupts the response.
     */
    private static final Set<String> STRIPPED_HEADERS = Set.of(
            "host", "connection", "keep-alive", "proxy-authenticate",
            "proxy-authorization", "te", "trailer", "transfer-encoding",
            "upgrade", "content-length", "expect");

    private final RestTemplate restTemplate;
    private final String baseUrl;
    private final String sharedSecret;

    public GatewayProxyController(RestTemplate gatewayProxyRestTemplate,
                                  @Value("${risk-engine.url}") String baseUrl,
                                  @Value("${risk-engine.shared-secret:}") String sharedSecret) {
        this.restTemplate = gatewayProxyRestTemplate;
        this.baseUrl = baseUrl;
        this.sharedSecret = sharedSecret;
    }

    @RequestMapping("/api/v1/**")
    public ResponseEntity<byte[]> proxy(HttpServletRequest request,
                                        @RequestBody(required = false) byte[] body) {

        URI target = UriComponentsBuilder.fromHttpUrl(baseUrl)
                .path(request.getRequestURI())
                .query(request.getQueryString())
                .build(true)
                .toUri();

        HttpMethod method = HttpMethod.valueOf(request.getMethod());
        HttpHeaders headers = copyHeaders(request);

        try {
            ResponseEntity<byte[]> response = restTemplate.exchange(
                    target, method, new HttpEntity<>(body, headers), byte[].class);

            // Relay the engine's own headers, minus the ones that describe the
            // upstream connection rather than the payload.
            HttpHeaders out = new HttpHeaders();
            response.getHeaders().forEach((name, values) -> {
                if (!STRIPPED_HEADERS.contains(name.toLowerCase())) {
                    out.put(name, values);
                }
            });
            return new ResponseEntity<>(response.getBody(), out, response.getStatusCode());

        } catch (ResourceAccessException ex) {
            log.error("Risk engine unreachable for {} {}: {}", method, target, ex.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(("{\"detail\":\"The risk engine is unreachable.\"}")
                            .getBytes(StandardCharsets.UTF_8));
        }
    }

    private HttpHeaders copyHeaders(HttpServletRequest request) {
        HttpHeaders headers = new HttpHeaders();
        var names = request.getHeaderNames();
        while (names.hasMoreElements()) {
            String name = names.nextElement();
            if (STRIPPED_HEADERS.contains(name.toLowerCase())) {
                continue;
            }
            headers.put(name, List.copyOf(java.util.Collections.list(request.getHeaders(name))));
        }
        // Identifies traffic as gateway-originated when the engine is configured
        // to require it; the caller's own Authorization header is left untouched.
        if (sharedSecret != null && !sharedSecret.isBlank()) {
            headers.set("X-Internal-Secret", sharedSecret);
        }
        return headers;
    }
}
