package com.cyberrisk.platform.config;

import com.cyberrisk.platform.model.Role;
// NOTE: adjust these two imports to match your actual User entity / repository package.
import com.cyberrisk.platform.model.User;
import com.cyberrisk.platform.repository.UserRepository;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Solves: "no way to create an ADMIN user" from the review.
 *
 * On every startup, if no ADMIN-role user exists, one is created from
 * env vars. This is idempotent (checked by role, not by re-running once),
 * so it's safe with the in-memory H2 profile that resets on every restart,
 * and it's a no-op once a real admin exists in a persistent (Postgres) DB.
 *
 * Required env vars:
 *   ADMIN_BOOTSTRAP_EMAIL
 *   ADMIN_BOOTSTRAP_PASSWORD   (must satisfy the same 12-char minimum as normal registration)
 *
 * If unset, bootstrap is skipped and a warning is logged — the app still
 * starts, it just means someone needs to set these before an admin can log in.
 */
@Configuration
public class AdminBootstrapConfig {

    @Bean
    public CommandLineRunner bootstrapAdmin(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            @Value("${ADMIN_BOOTSTRAP_EMAIL:}") String adminEmail,
            @Value("${ADMIN_BOOTSTRAP_PASSWORD:}") String adminPassword) {

        return args -> {
            boolean adminExists = userRepository.existsByRole(Role.ADMIN);
            if (adminExists) {
                return;
            }

            if (adminEmail.isBlank() || adminPassword.isBlank()) {
                System.err.println(
                    "[AdminBootstrap] No ADMIN user exists and ADMIN_BOOTSTRAP_EMAIL / " +
                    "ADMIN_BOOTSTRAP_PASSWORD are not set. Skipping admin creation — " +
                    "set both env vars and restart to bootstrap an admin."
                );
                return;
            }

            if (adminPassword.length() < 12) {
                System.err.println(
                    "[AdminBootstrap] ADMIN_BOOTSTRAP_PASSWORD is shorter than the required " +
                    "12 characters. Skipping admin creation."
                );
                return;
            }

            User admin = new User();
            admin.setEmail(adminEmail);
            admin.setPasswordHash(passwordEncoder.encode(adminPassword));
            admin.setRole(Role.ADMIN);
            userRepository.save(admin);

            System.out.println("[AdminBootstrap] Created initial ADMIN user: " + adminEmail);
        };
    }
}

/*
 * Add this method to UserRepository (extends JpaRepository<User, UUID> or similar):
 *
 *   boolean existsByRole(Role role);
 */
