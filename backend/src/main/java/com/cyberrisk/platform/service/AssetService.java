package com.cyberrisk.platform.service;

import com.cyberrisk.platform.domain.Asset;
import com.cyberrisk.platform.dto.AssetRequest;
import com.cyberrisk.platform.dto.AssetResponse;
import com.cyberrisk.platform.repository.AssetRepository;
import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AssetService {

    private final AssetRepository assetRepository;

    @Transactional
    public AssetResponse create(AssetRequest request) {

        Asset asset = Asset.builder()
                .name(request.name())
                .assetType(request.assetType())
                .businessUnit(request.businessUnit())
                .criticality(request.criticality())
                .annualBusinessValue(request.annualBusinessValue())
                .sensitiveRecordCount(request.sensitiveRecordCount())
                .build();

        return AssetResponse.from(assetRepository.save(asset));
    }

    @Transactional(readOnly = true)
    public List<AssetResponse> findAll() {

        return assetRepository.findAll()
                .stream()
                .map(AssetResponse::from)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public AssetResponse findById(String id) {

        return AssetResponse.from(getOrThrow(id));
    }

    @Transactional
    public AssetResponse update(String id, AssetRequest request) {

        Asset asset = getOrThrow(id);

        asset.setName(request.name());
        asset.setAssetType(request.assetType());
        asset.setBusinessUnit(request.businessUnit());
        asset.setCriticality(request.criticality());
        asset.setAnnualBusinessValue(request.annualBusinessValue());
        asset.setSensitiveRecordCount(request.sensitiveRecordCount());

        return AssetResponse.from(assetRepository.save(asset));
    }

    @Transactional
    public void delete(String id) {

        if (!assetRepository.existsById(id)) {
            throw new EntityNotFoundException(
                    "Asset not found: " + id
            );
        }

        assetRepository.deleteById(id);
    }

    private Asset getOrThrow(String id) {

        return assetRepository.findById(id)
                .orElseThrow(() ->
                        new EntityNotFoundException(
                                "Asset not found: " + id
                        )
                );
    }
}