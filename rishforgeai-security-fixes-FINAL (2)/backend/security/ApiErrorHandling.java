package com.cyberrisk.platform.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.io.IOException;
import java.util.Map;

/**
 * Keeps every error response — including auth failures that Spring Security
 * generates before a controller is ever reached — in the project's standard
 * {success, data, message} shape, and never leaks stack traces or internal
 * exception detail to the client.
 */

// Handles 401s: no/invalid/expired token.
@Component
class ApiAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                          AuthenticationException authException) throws IOException {
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setContentType("application/json");
        response.getWriter().write(
            "{\"success\":false,\"data\":null,\"message\":\"Authentication required.\"}"
        );
    }
}

// Handles 403s: valid token, but role doesn't satisfy @PreAuthorize.
@Component
class ApiAccessDeniedHandler implements AccessDeniedHandler {
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                        AccessDeniedException accessDeniedException) throws IOException {
        response.setStatus(HttpStatus.FORBIDDEN.value());
        response.setContentType("application/json");
        response.getWriter().write(
            "{\"success\":false,\"data\":null,\"message\":\"You do not have permission to perform this action.\"}"
        );
    }
}

// Handles everything else (validation errors, unhandled exceptions) the
// same way, for any request that does reach a controller.
@RestControllerAdvice
class ApiExceptionHandler {

    @ExceptionHandler(org.springframework.web.bind.MethodArgumentNotValidException.class)
    public ResponseEntity<?> handleValidation(org.springframework.web.bind.MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .orElse("Validation failed.");
        return ResponseEntity.badRequest()
                .body(Map.of("success", false, "data", "", "message", message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleGeneric(Exception ex) {
        // Never expose ex.getMessage()/stack trace to the client (matches the
        // existing pattern of not leaking JWT parser errors) — log server-side
        // instead if you have logging configured.
        return ResponseEntity.internalServerError()
                .body(Map.of("success", false, "data", "", "message", "An unexpected error occurred."));
    }
}

/*
 * Wire the two @Component beans into SecurityConfig's filterChain():
 *
 *   http.exceptionHandling(ex -> ex
 *       .authenticationEntryPoint(apiAuthenticationEntryPoint)
 *       .accessDeniedHandler(apiAccessDeniedHandler)
 *   );
 *
 * (inject both via constructor, same as jwtAuthenticationFilter/rateLimitFilter)
 */
