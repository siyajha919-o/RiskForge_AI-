package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.ControlRequest;
import com.cyberrisk.platform.dto.ControlResponse;
import com.cyberrisk.platform.service.ControlService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/controls")
@RequiredArgsConstructor
public class ControlController {

    private final ControlService controlService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ControlResponse create(
            @Valid @RequestBody ControlRequest request) {

        return controlService.create(request);
    }

    @GetMapping
    public List<ControlResponse> findAll(
            @RequestParam(required = false) String assetId) {

        return assetId != null
                ? controlService.findByAsset(assetId)
                : controlService.findAll();
    }
}