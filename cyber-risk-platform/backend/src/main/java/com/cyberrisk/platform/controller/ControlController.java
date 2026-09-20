package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.ControlRequest;
import com.cyberrisk.platform.dto.ControlResponse;
import com.cyberrisk.platform.service.ControlService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/platform/controls")
@RequiredArgsConstructor
public class ControlController {

    private final ControlService controlService;

    @PreAuthorize("hasAnyRole('ANALYST','CISO','ADMIN')")
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ControlResponse create(@Valid @RequestBody ControlRequest request) {
        return controlService.create(request);
    }

    @PreAuthorize("hasAnyRole('VIEWER','ANALYST','CISO','ADMIN')")
    @GetMapping
    public List<ControlResponse> findAll(@RequestParam(required = false) UUID assetId) {
        return assetId != null ? controlService.findByAsset(assetId) : controlService.findAll();
    }
}
