package com.cyberrisk.platform.security;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory, per-client-IP rate limiting.
 *
 * Two tiers:
 *  - LOGIN_BUCKET: tight limit on /api/v1/auth/login to blunt
 *    credential-stuffing / brute force (the gap called out in the review).
 *  - GENERAL_BUCKET: looser limit for everything else so the API
 *    isn't trivially hammered.
 *
 * Note: in-memory buckets reset on restart and don't share state across
 * multiple backend instances. For a single-instance hackathon deployment
 * that's fine; for real horizontal scaling, back this with Redis instead
 * (bucket4j has a redis-based ProxyManager for that).
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private final ConcurrentHashMap<String, Bucket> loginBuckets = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Bucket> generalBuckets = new ConcurrentHashMap<>();

    private Bucket newLoginBucket() {
        // 5 attempts per minute per IP
        Bandwidth limit = Bandwidth.classic(5, Refill.intervally(5, Duration.ofMinutes(1)));
        return Bucket.builder().addLimit(limit).build();
    }

    private Bucket newGeneralBucket() {
        // 120 requests per minute per IP
        Bandwidth limit = Bandwidth.classic(120, Refill.intervally(120, Duration.ofMinutes(1)));
        return Bucket.builder().addLimit(limit).build();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {

        String clientIp = resolveClientIp(request);
        boolean isLogin = "/api/v1/auth/login".equals(request.getRequestURI());

        Bucket bucket = isLogin
                ? loginBuckets.computeIfAbsent(clientIp, ip -> newLoginBucket())
                : generalBuckets.computeIfAbsent(clientIp, ip -> newGeneralBucket());

        if (bucket.tryConsume(1)) {
            filterChain.doFilter(request, response);
        } else {
            response.setStatus(429); // 429 Too Many Requests
            response.setContentType("application/json");
            response.getWriter().write(
                "{\"success\":false,\"data\":null,\"message\":\"Too many requests. Please try again shortly.\"}"
            );
        }
    }

    private String resolveClientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
