package com.cyberrisk.platform.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.util.Date;
import java.util.List;

@Service
public class JwtService {

    private final SecretKey signingKey;
    private final long expirationMillis;

    public JwtService(
            @Value("${security.jwt.secret}") String secret, // env-backed, no hardcoded fallback (kept as-is)
            @Value("${security.jwt.expiration-minutes:60}") long expirationMinutes) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException(
                "security.jwt.secret is not configured. Set the JWT_SECRET environment variable."
            );
        }
        this.signingKey = Keys.hmacShaKeyFor(secret.getBytes());
        this.expirationMillis = expirationMinutes * 60_000;
    }

    public String generateToken(String userId, String email, String role) {
        Date now = new Date();
        Date expiry = new Date(now.getTime() + expirationMillis);

        return Jwts.builder()
                .setSubject(userId)
                .claim("email", email)
                .claim("role", role) // single role claim; see Role enum (ADMIN/ANALYST/CISO/VIEWER)
                .setIssuedAt(now)
                .setExpiration(expiry)
                .signWith(signingKey, SignatureAlgorithm.HS256)
                .compact();
    }

    /** Returns claims if valid, or throws (caller should catch and treat as unauthenticated). */
    public Claims parseAndValidate(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(signingKey)
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    public List<String> extractRole(Claims claims) {
        Object role = claims.get("role");
        return role == null ? List.of() : List.of("ROLE_" + role);
    }
}
