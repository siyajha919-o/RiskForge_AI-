package com.cyberrisk.platform.security;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Per-client-IP rate limiting: a tight bucket on login to blunt credential
 * stuffing, and a looser one for everything else.
 *
 * Buckets are in-memory, so they reset on restart and are per-instance. That is
 * fine for a single-instance deployment; horizontal scaling needs bucket4j's
 * Redis ProxyManager instead.
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    /**
     * Both login surfaces get the tight bucket: this service's own, and the
     * engine's as reached through the gateway passthrough. Missing the proxied
     * one would leave the credential-stuffing path wide open now that the
     * dashboard signs in through here.
     */
    private static final Set<String> LOGIN_PATHS = Set.of(
            "/api/v1/platform/auth/login", "/api/v1/auth/login");

    private final ConcurrentHashMap<String, Bucket> loginBuckets = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Bucket> generalBuckets = new ConcurrentHashMap<>();

    /**
     * Only trust X-Forwarded-For when actually running behind a reverse proxy.
     * Trusting it unconditionally makes the limiter useless: an attacker just
     * varies the header to get a fresh bucket on every request.
     */
    private final boolean trustForwardedHeader;

    public RateLimitFilter(@Value("${security.rate-limit.trust-forwarded-header:false}") boolean trustForwardedHeader) {
        this.trustForwardedHeader = trustForwardedHeader;
    }

    private static Bucket loginBucket() {
        return Bucket.builder()
                .addLimit(Bandwidth.classic(5, Refill.intervally(5, Duration.ofMinutes(1))))
                .build();
    }

    private static Bucket generalBucket() {
        return Bucket.builder()
                .addLimit(Bandwidth.classic(120, Refill.intervally(120, Duration.ofMinutes(1))))
                .build();
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                    @NonNull HttpServletResponse response,
                                    @NonNull FilterChain filterChain)
            throws ServletException, IOException {

        String clientIp = resolveClientIp(request);
        boolean isLogin = LOGIN_PATHS.contains(request.getRequestURI());

        Bucket bucket = isLogin
                ? loginBuckets.computeIfAbsent(clientIp, ip -> loginBucket())
                : generalBuckets.computeIfAbsent(clientIp, ip -> generalBucket());

        if (bucket.tryConsume(1)) {
            filterChain.doFilter(request, response);
            return;
        }

        response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
        response.setContentType("application/json");
        response.getWriter().write(
                "{\"timestamp\":\"" + java.time.Instant.now() + "\","
                        + "\"message\":\"Too many requests. Please try again shortly.\"}");
    }

    private String resolveClientIp(HttpServletRequest request) {
        if (trustForwardedHeader) {
            String forwarded = request.getHeader("X-Forwarded-For");
            if (forwarded != null && !forwarded.isBlank()) {
                return forwarded.split(",")[0].trim();
            }
        }
        return request.getRemoteAddr();
    }
}
