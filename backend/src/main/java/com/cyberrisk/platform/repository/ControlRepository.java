package com.cyberrisk.platform.repository;

import com.cyberrisk.platform.domain.Control;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface ControlRepository
        extends JpaRepository<Control, UUID> {

    List<Control> findByAssetId(String assetId);

    List<Control> findByAssetIdAndImplementedTrue(
            String assetId
    );
}