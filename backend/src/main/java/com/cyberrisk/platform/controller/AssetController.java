package com.cyberrisk.platform.controller;

import com.cyberrisk.platform.dto.AssetRequest;
import com.cyberrisk.platform.dto.AssetResponse;
import com.cyberrisk.platform.service.AssetService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/assets")
@RequiredArgsConstructor
public class AssetController {

    private final AssetService assetService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public AssetResponse create(@Valid @RequestBody AssetRequest request) {
        return assetService.create(request);
    }

    @GetMapping
    public List<AssetResponse> findAll() {
        return assetService.findAll();
    }

    @GetMapping("/{id}")
    public AssetResponse findById(@PathVariable String id) {
        return assetService.findById(id);
    }

    @PutMapping("/{id}")
    public AssetResponse update(
            @PathVariable String id,
            @Valid @RequestBody AssetRequest request) {

        return assetService.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable String id) {
        assetService.delete(id);
    }
}