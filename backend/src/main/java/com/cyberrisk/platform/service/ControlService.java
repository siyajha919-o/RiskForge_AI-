package com.cyberrisk.platform.service;

import com.cyberrisk.platform.domain.Asset;
import com.cyberrisk.platform.domain.Control;
import com.cyberrisk.platform.dto.ControlRequest;
import com.cyberrisk.platform.dto.ControlResponse;
import com.cyberrisk.platform.repository.AssetRepository;
import com.cyberrisk.platform.repository.ControlRepository;

import jakarta.persistence.EntityNotFoundException;

import lombok.RequiredArgsConstructor;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ControlService {

    private final ControlRepository controlRepository;
    private final AssetRepository assetRepository;

    @Transactional
    public ControlResponse create(ControlRequest request) {

        Asset asset = assetRepository.findById(request.assetId())
                .orElseThrow(() ->
                        new EntityNotFoundException(
                                "Asset not found: " + request.assetId()
                        )
                );

        Control control = Control.builder()
                .asset(asset)
                .name(request.name())
                .description(request.description())
                .controlType(request.controlType())
                .effectivenessScore(request.effectivenessScore())
                .implemented(request.implemented())
                .annualCost(request.annualCost())
                .frameworkMappings(
                        request.frameworkMappings() == null
                                ? new ArrayList<>()
                                : request.frameworkMappings()
                )
                .build();

        Control savedControl = controlRepository.save(control);

        return ControlResponse.from(savedControl);
    }

    @Transactional(readOnly = true)
    public List<ControlResponse> findByAsset(String assetId) {

        return controlRepository.findByAssetId(assetId)
                .stream()
                .map(ControlResponse::from)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<ControlResponse> findAll() {

        return controlRepository.findAll()
                .stream()
                .map(ControlResponse::from)
                .collect(Collectors.toList());
    }
}