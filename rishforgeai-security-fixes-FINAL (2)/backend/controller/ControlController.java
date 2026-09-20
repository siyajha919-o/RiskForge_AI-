package com.cyberrisk.platform.controller;

import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

/**
 * Same role pattern as AssetController: VIEWER can read, ANALYST/CISO/ADMIN
 * can write. Inject your existing ControlService as before — only the
 * @PreAuthorize annotations are new.
 */
@RestController
@RequestMapping("/api/v1/controls")
public class ControlController {

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping
    public ResponseEntity<?> listControls(@RequestParam(required = false) UUID assetId) {
        return ResponseEntity.ok().build();
    }

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping
    public ResponseEntity<?> createControl(@Valid @RequestBody Object request) {
        return ResponseEntity.ok().build();
    }
}
