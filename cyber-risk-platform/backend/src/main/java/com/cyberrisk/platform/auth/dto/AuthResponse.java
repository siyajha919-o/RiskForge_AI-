package com.cyberrisk.platform.auth.dto;

public record AuthResponse(String accessToken, String tokenType, String role, long expiresInMinutes) {
    public static AuthResponse of(String token, String role, long expiresInMinutes) {
        return new AuthResponse(token, "Bearer", role, expiresInMinutes);
    }
}
