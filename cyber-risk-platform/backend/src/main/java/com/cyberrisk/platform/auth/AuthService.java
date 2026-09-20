package com.cyberrisk.platform.auth;

import com.cyberrisk.platform.auth.dto.AuthResponse;
import com.cyberrisk.platform.auth.dto.LoginRequest;
import com.cyberrisk.platform.auth.dto.RegisterRequest;
import com.cyberrisk.platform.domain.Role;
import com.cyberrisk.platform.domain.User;
import com.cyberrisk.platform.repository.UserRepository;
import com.cyberrisk.platform.security.JwtService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;

    /**
     * New accounts always get the least-privileged role. Promotion is an
     * admin-only action so a registration payload can never request its own
     * privilege level.
     */
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already registered");
        }

        User user = User.builder()
                .email(request.email())
                .passwordHash(passwordEncoder.encode(request.password()))
                .role(Role.VIEWER)
                .enabled(true)
                .build();
        userRepository.save(user);

        return token(user);
    }

    public AuthResponse login(LoginRequest request) {
        authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password()));

        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));

        return token(user);
    }

    private AuthResponse token(User user) {
        String jwt = jwtService.generateToken(user, Map.of("role", user.getRole().name()));
        return AuthResponse.of(jwt, user.getRole().name(), jwtService.getExpirationMinutes());
    }
}
