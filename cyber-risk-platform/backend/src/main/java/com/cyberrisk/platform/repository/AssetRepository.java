package com.cyberrisk.platform.repository;

import com.cyberrisk.platform.domain.Asset;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface AssetRepository extends JpaRepository<Asset, UUID> {
}
