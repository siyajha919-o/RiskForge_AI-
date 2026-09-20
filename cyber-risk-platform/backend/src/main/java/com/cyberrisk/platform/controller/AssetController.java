package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.AssetRequest;
import com.cyberrisk.platform.dto.AssetResponse;
import com.cyberrisk.platform.service.AssetService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/platform/assets")
@RequiredArgsConstructor
public class AssetController {

    private final AssetService assetService;

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public AssetResponse create(@Valid @RequestBody AssetRequest request) {
        return assetService.create(request);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping
    public List<AssetResponse> findAll() {
        return assetService.findAll();
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping("/{id}")
    public AssetResponse findById(@PathVariable UUID id) {
        return assetService.findById(id);
    }

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PutMapping("/{id}")
    public AssetResponse update(@PathVariable UUID id, @Valid @RequestBody AssetRequest request) {
        return assetService.update(id, request);
    }

    @PreAuthorize("hasRole('ADMIN')")
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id) {
        assetService.delete(id);
    }
}
