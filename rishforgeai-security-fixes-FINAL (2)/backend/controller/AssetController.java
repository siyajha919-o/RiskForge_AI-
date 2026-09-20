package com.cyberrisk.platform.controller;

import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

/**
 * Example of applying the role checks that were previously missing.
 * Apply the same @PreAuthorize pattern to ControlController and
 * VulnerabilityController: VIEWER can read, ANALYST/CISO/ADMIN can write,
 * only ADMIN can delete.
 *
 * Roles here are Spring Security authorities, so they must match what
 * JwtService.extractRole() emits: "ROLE_ADMIN", "ROLE_ANALYST", etc.
 */
@RestController
@RequestMapping("/api/v1/assets")
public class AssetController {

    // Inject your existing AssetService here as before — only the
    // annotations below are new.

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping
    public ResponseEntity<?> listAssets() {
        // unchanged existing logic
        return ResponseEntity.ok().build();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/{id}")
    public ResponseEntity<?> getAsset(@PathVariable UUID id) {
        return ResponseEntity.ok().build();
    }

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping
    public ResponseEntity<?> createAsset(@Valid @RequestBody Object request) {
        return ResponseEntity.ok().build();
    }

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PutMapping("/{id}")
    public ResponseEntity<?> updateAsset(@PathVariable UUID id, @Valid @RequestBody Object request) {
        return ResponseEntity.ok().build();
    }

    @PreAuthorize("hasRole('ADMIN')")
    @DeleteMapping("/{id}")
    public ResponseEntity<?> deleteAsset(@PathVariable UUID id) {
        return ResponseEntity.ok().build();
    }
}
