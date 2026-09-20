package com.cyberrisk.platform.config;

import com.cyberrisk.platform.domain.Role;
import com.cyberrisk.platform.domain.User;
import com.cyberrisk.platform.repository.UserRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Creates the first ADMIN account, since registration deliberately cannot
 * grant that role. Idempotent: skipped once any ADMIN exists, so it is a
 * no-op against a persistent database and re-seeds the in-memory demo profile
 * on each restart.
 */
@Slf4j
@Configuration
public class AdminBootstrapConfig {

    @Bean
    public CommandLineRunner bootstrapAdmin(UserRepository userRepository,
                                            PasswordEncoder passwordEncoder,
                                            @Value("${security.admin-bootstrap.email:}") String email,
                                            @Value("${security.admin-bootstrap.password:}") String password) {
        return args -> {
            if (userRepository.existsByRole(Role.ADMIN)) {
                return;
            }
            if (email.isBlank() || password.isBlank()) {
                log.warn("No ADMIN exists and ADMIN_BOOTSTRAP_EMAIL/PASSWORD are unset — "
                        + "set both and restart to create the first admin.");
                return;
            }
            if (password.length() < 12) {
                log.warn("ADMIN_BOOTSTRAP_PASSWORD is shorter than 12 characters — admin not created.");
                return;
            }

            userRepository.save(User.builder()
                    .email(email)
                    .passwordHash(passwordEncoder.encode(password))
                    .role(Role.ADMIN)
                    .enabled(true)
                    .build());
            log.info("Created initial ADMIN user: {}", email);
        };
    }
}
