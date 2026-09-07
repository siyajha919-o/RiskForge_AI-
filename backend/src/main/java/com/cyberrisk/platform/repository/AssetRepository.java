package com.cyberrisk.platform.repository;

import com.cyberrisk.platform.domain.Asset;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AssetRepository extends JpaRepository<Asset, String> {
}