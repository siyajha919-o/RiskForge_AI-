package com.cyberrisk.platform.repository;

import com.cyberrisk.platform.domain.RiskSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface RiskSnapshotRepository
        extends JpaRepository<RiskSnapshot, UUID> {

    List<RiskSnapshot> findByAssetIdOrderByCalculatedAtDesc(
            String assetId
    );
}