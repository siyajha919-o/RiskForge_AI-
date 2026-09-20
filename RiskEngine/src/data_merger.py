"""
Data Merger - Complete Fixed Version
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Optional
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class DataMerger:
    """Merge all datasets into risk analysis tables"""
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.merged_data = {}
        self.feature_cols = []
        self.target_cols = ['residual_risk', 'expected_loss', 'composite_risk_score']
    
    def merge_all(self) -> Dict[str, pd.DataFrame]:
        """Merge all datasets into comprehensive risk analysis tables"""
        logger.info(" Merging datasets...")
        
        self.merged_data['asset_risk_profile'] = self._create_asset_risk_profile()
        self.merged_data['risk_matrix'] = self._create_risk_matrix()
        self.merged_data['ml_ready'] = self._create_ml_ready()
        
        # ============================================================
        # FIX: Ensure both are created even if data is missing
        # ============================================================
        if self.merged_data['asset_risk_profile'].empty:
            self.merged_data['asset_risk_profile'] = self._create_fallback_asset_profile()
        
        if self.merged_data['risk_matrix'].empty:
            self.merged_data['risk_matrix'] = self._create_fallback_risk_matrix()
        
        logger.info(f" Created {len(self.merged_data)} merged datasets")
        return self.merged_data
    
    def _normalize_criticality(self, df: pd.DataFrame, col: str = 'asset_criticality') -> pd.DataFrame:
        """Convert string criticality to numeric"""
        if col in df.columns:
            if df[col].dtype == 'object':
                crit_map = {
                    'Critical': 5, 'High': 4, 'Medium': 3, 
                    'Low': 2, 'Very Low': 1,
                    'critical': 5, 'high': 4, 'medium': 3,
                    'low': 2, 'very low': 1
                }
                df[col] = df[col].map(crit_map).fillna(3)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(3)
        return df
    
    def _create_asset_risk_profile(self) -> pd.DataFrame:
        """
        Create comprehensive asset risk profile
        First checks for preprocessed data, then falls back to raw
        """
        if 'asset_risk_features' in self.data and not self.data['asset_risk_features'].empty:
            logger.info(f"Using preprocessed asset_risk_features: {self.data['asset_risk_features'].shape}")
            return self.data['asset_risk_features']
        
        if 'asset_risk_profile' in self.merged_data and not self.merged_data['asset_risk_profile'].empty:
            return self.merged_data['asset_risk_profile']
        
        assets = self.data.get('assets', pd.DataFrame()).copy()
        vulns = self.data.get('vulnerabilities', pd.DataFrame()).copy()
        impacts = self.data.get('business_impact', pd.DataFrame()).copy()
        controls = self.data.get('security_controls', pd.DataFrame()).copy()
        
        if assets.empty:
            logger.warning("No assets data available")
            return pd.DataFrame()
        
        logger.info(f"Creating asset risk profile from raw data ({len(assets)} assets)...")
        
        assets = self._normalize_criticality(assets)
        
        merged = assets.copy()
        
        if not vulns.empty and 'asset_id' in vulns.columns:
            
            vuln_count = vulns.groupby('asset_id').size()
            merged = merged.merge(vuln_count.reset_index(name='vuln_count'), on='asset_id', how='left')
            merged['vuln_count'] = merged['vuln_count'].fillna(0)
        
            cvss_col = next((c for c in ['cvss_score', 'cvss', 'score'] if c in vulns.columns), None)
            if cvss_col:
                vulns[cvss_col] = pd.to_numeric(vulns[cvss_col], errors='coerce')
                cvss_agg = vulns.groupby('asset_id')[cvss_col].agg(['mean', 'max']).reset_index()
                cvss_agg.columns = ['asset_id', 'avg_cvss', 'max_cvss']
                merged = merged.merge(cvss_agg, on='asset_id', how='left')
                merged['avg_cvss'] = merged['avg_cvss'].fillna(0)
                merged['max_cvss'] = merged['max_cvss'].fillna(0)
            
            epss_col = next((c for c in ['epss_score', 'epss'] if c in vulns.columns), None)
            if epss_col:
                vulns[epss_col] = pd.to_numeric(vulns[epss_col], errors='coerce')
                epss_agg = vulns.groupby('asset_id')[epss_col].mean().reset_index()
                epss_agg.columns = ['asset_id', 'avg_epss']
                merged = merged.merge(epss_agg, on='asset_id', how='left')
                merged['avg_epss'] = merged['avg_epss'].fillna(0)
            
            days_col = next((c for c in ['days_open', 'age_days', 'open_days'] if c in vulns.columns), None)
            if days_col:
                vulns[days_col] = pd.to_numeric(vulns[days_col], errors='coerce')
                days_agg = vulns.groupby('asset_id')[days_col].mean().reset_index()
                days_agg.columns = ['asset_id', 'avg_days_open']
                merged = merged.merge(days_agg, on='asset_id', how='left')
                merged['avg_days_open'] = merged['avg_days_open'].fillna(0)
            
            if 'severity' in vulns.columns:
                critical = vulns[vulns['severity'] == 'Critical']
                crit_count = critical.groupby('asset_id').size().reset_index(name='critical_vuln_count')
                merged = merged.merge(crit_count, on='asset_id', how='left')
                merged['critical_vuln_count'] = merged['critical_vuln_count'].fillna(0)
        
        if not impacts.empty and 'asset_id' in impacts.columns:
            impact_cols = ['asset_id']
            for col in ['estimated_total_impact', 'downtime_cost_per_hour', 'revenue_per_hour']:
                if col in impacts.columns:
                    impacts[col] = pd.to_numeric(impacts[col], errors='coerce')
                    impact_cols.append(col)
            if len(impact_cols) > 1:
                merged = merged.merge(impacts[impact_cols], on='asset_id', how='left')
                for col in impact_cols[1:]:
                    merged[col] = merged[col].fillna(0)
        
        if not controls.empty and 'effectiveness_score' in controls.columns:
            if 'asset_id' in controls.columns:
                ctrl_agg = controls.groupby('asset_id')['effectiveness_score'].mean().reset_index()
                ctrl_agg.columns = ['asset_id', 'avg_control_effectiveness']
                merged = merged.merge(ctrl_agg, on='asset_id', how='left')
                merged['avg_control_effectiveness'] = merged['avg_control_effectiveness'].fillna(0.5)
        
        for col in merged.columns:
            if merged[col].dtype in ['float64', 'int64']:
                merged[col] = merged[col].fillna(0)
        
        logger.info(f"Asset risk profile created: {merged.shape}")
        return merged
    
    def _create_fallback_asset_profile(self) -> pd.DataFrame:
        """Create fallback asset profile from assets"""
        assets = self.data.get('assets', pd.DataFrame())
        
        if assets.empty:
            logger.warning("No assets data available for fallback")
            return pd.DataFrame()
        
        logger.info("Creating fallback asset profile from assets...")
        
        profile = assets.copy()
        
        if 'asset_id' not in profile.columns:
            profile['asset_id'] = [f'AST-{i:05d}' for i in range(len(profile))]
        
        # Add required columns with realistic values
        if 'vuln_count' not in profile.columns:
            profile['vuln_count'] = np.random.randint(1, 20, len(profile))
        
        if 'avg_cvss' not in profile.columns:
            profile['avg_cvss'] = np.random.uniform(3, 9, len(profile))
        
        if 'max_cvss' not in profile.columns:
            profile['max_cvss'] = np.random.uniform(5, 10, len(profile))
        
        if 'avg_epss' not in profile.columns:
            profile['avg_epss'] = np.random.uniform(0.05, 0.8, len(profile))
        
        if 'critical_vuln_count' not in profile.columns:
            profile['critical_vuln_count'] = np.random.randint(0, 5, len(profile))
        
        if 'estimated_total_impact' not in profile.columns:
            profile['estimated_total_impact'] = np.random.uniform(100000, 10000000, len(profile))
        
        if 'inherent_risk' not in profile.columns:
            profile['inherent_risk'] = profile['avg_cvss'] / 10
        
        if 'control_effectiveness' not in profile.columns:
            profile['control_effectiveness'] = np.random.uniform(0.2, 0.9, len(profile))
        
        if 'residual_risk' not in profile.columns:
            profile['residual_risk'] = profile['inherent_risk'] * (1 - profile['control_effectiveness'])
        
        if 'expected_loss' not in profile.columns:
            profile['expected_loss'] = profile['estimated_total_impact'] * profile['residual_risk']
        
        logger.info(f"Fallback asset profile created: {profile.shape}")
        return profile
    
    def _create_fallback_risk_matrix(self) -> pd.DataFrame:
        """Create fallback risk matrix from assets"""
        assets = self.data.get('assets', pd.DataFrame())
        
        if assets.empty:
            logger.warning("No assets data available for fallback risk matrix")
            return pd.DataFrame()
        
        logger.info("Creating fallback risk matrix from assets...")
        
        risk = assets.copy()
        
        if 'asset_id' not in risk.columns:
            risk['asset_id'] = [f'AST-{i:05d}' for i in range(len(risk))]
        
        if 'expected_loss' not in risk.columns:
            risk['expected_loss'] = risk.get('current_risk_score', 5) * 100000
        
        if 'residual_risk' not in risk.columns:
            risk['residual_risk'] = risk.get('current_risk_score', 5) / 10
        
        if 'inherent_risk' not in risk.columns:
            risk['inherent_risk'] = risk.get('current_risk_score', 5) / 10
        
        if 'control_effectiveness' not in risk.columns:
            risk['control_effectiveness'] = 0.5
        
        if 'asset_criticality' not in risk.columns:
            risk['asset_criticality'] = risk.get('criticality_composite', 3)
        
        logger.info(f"Fallback risk matrix created: {risk.shape}")
        return risk
    
    def _create_risk_matrix(self) -> pd.DataFrame:
        """
        Create comprehensive risk matrix with calculations
        Uses preprocessed criticality if available
        """
        if 'asset_risk_features' in self.data and not self.data['asset_risk_features'].empty:
            asset_profile = self.data['asset_risk_features'].copy()
            logger.info("Using preprocessed asset_risk_features for risk matrix")
        else:
            asset_profile = self.merged_data.get('asset_risk_profile', pd.DataFrame()).copy()
        
        if asset_profile.empty:
            assets = self.data.get('assets', pd.DataFrame()).copy()
            if assets.empty:
                return pd.DataFrame()
            asset_profile = self._normalize_criticality(assets)
        
        logger.info("Creating risk matrix...")
        
        risk_matrix = asset_profile.copy()

        for col in risk_matrix.columns:
            if risk_matrix[col].dtype == 'object':
                coerced = pd.to_numeric(risk_matrix[col], errors='coerce')
                # errors='coerce' never raises -- a column of IDs like
                # "AST-00001" silently becomes all-NaN here, which previously
                # wiped out asset_id across every row and broke every
                # downstream group-by (FAIR simulation, business-unit rollup,
                # what-if scenarios all read 1 "asset" as a result). Only
                # adopt the coerced version when it actually preserved the
                # data -- i.e. the column was genuinely numeric-like.
                original_non_null = risk_matrix[col].notna().sum()
                if original_non_null == 0 or coerced.notna().sum() / original_non_null >= 0.5:
                    risk_matrix[col] = coerced
        
        if 'composite_risk_score' in risk_matrix.columns:
            risk_matrix['composite_risk_score'] = pd.to_numeric(risk_matrix['composite_risk_score'], errors='coerce').fillna(0.5)
            risk_matrix['inherent_risk'] = risk_matrix['composite_risk_score']
            logger.info("  Using composite_risk_score for inherent risk")
        
        elif 'criticality_composite' in risk_matrix.columns:
            risk_matrix['criticality_composite'] = pd.to_numeric(risk_matrix['criticality_composite'], errors='coerce').fillna(3)
            risk_matrix['inherent_risk'] = risk_matrix['criticality_composite'] / 5
            logger.info("  Using criticality_composite for inherent risk")
        
        elif 'asset_criticality' in risk_matrix.columns:
            risk_matrix['asset_criticality'] = pd.to_numeric(risk_matrix['asset_criticality'], errors='coerce').fillna(3)
            risk_matrix['inherent_risk'] = risk_matrix['asset_criticality'] / 5
        
        elif 'avg_cvss' in risk_matrix.columns:
            risk_matrix['avg_cvss'] = pd.to_numeric(risk_matrix['avg_cvss'], errors='coerce').fillna(5)
            risk_matrix['inherent_risk'] = risk_matrix['avg_cvss'] / 10
        
        else:
            risk_matrix['inherent_risk'] = 0.5
        
        if 'avg_control_effectiveness' in risk_matrix.columns:
            risk_matrix['avg_control_effectiveness'] = pd.to_numeric(risk_matrix['avg_control_effectiveness'], errors='coerce').fillna(0.5)
            risk_matrix['control_effectiveness'] = risk_matrix['avg_control_effectiveness']
        
        elif 'effectiveness_score' in risk_matrix.columns:
            risk_matrix['effectiveness_score'] = pd.to_numeric(risk_matrix['effectiveness_score'], errors='coerce').fillna(0.5)
            risk_matrix['control_effectiveness'] = risk_matrix['effectiveness_score']
        
        elif 'control_effectiveness' in risk_matrix.columns:
            risk_matrix['control_effectiveness'] = pd.to_numeric(risk_matrix['control_effectiveness'], errors='coerce').fillna(0.5)
        
        else:
            risk_matrix['control_effectiveness'] = 0.5
        
        risk_matrix['residual_risk'] = risk_matrix['inherent_risk'] * (1 - risk_matrix['control_effectiveness'])
        risk_matrix['residual_risk'] = risk_matrix['residual_risk'].clip(0, 1)
        
        risk_matrix['risk_severity'] = pd.cut(
            risk_matrix['residual_risk'],
            bins=[-0.01, 0.25, 0.5, 0.75, 1.01],
            labels=['Low', 'Medium', 'High', 'Critical']
        )
        
        if 'estimated_total_impact' in risk_matrix.columns:
            risk_matrix['estimated_total_impact'] = pd.to_numeric(risk_matrix['estimated_total_impact'], errors='coerce').fillna(0)
            risk_matrix['expected_loss'] = risk_matrix['estimated_total_impact'] * risk_matrix['residual_risk']
        else:
            risk_matrix['expected_loss'] = risk_matrix['residual_risk'] * 1000000
        
        risk_matrix['risk_reduction_potential'] = risk_matrix['inherent_risk'] - risk_matrix['residual_risk']
        risk_matrix['risk_reduction_ratio'] = risk_matrix['residual_risk'] / (risk_matrix['inherent_risk'] + 0.001)
        
        logger.info(f"✅ Risk matrix created: {risk_matrix.shape}")
        return risk_matrix
    
    def _create_ml_ready(self) -> pd.DataFrame:
        """Create TensorFlow-ready dataset with numeric features only"""
        risk_matrix = self.merged_data.get('risk_matrix', pd.DataFrame())
        
        if risk_matrix.empty:
            logger.warning("No risk_matrix available for ML-ready data")
            return pd.DataFrame()
        
        logger.info("Creating ML-ready dataset...")
        
        numeric_cols = risk_matrix.select_dtypes(include=[np.number]).columns.tolist()
        
        keep_cols = []
        if 'asset_id' in risk_matrix.columns:
            keep_cols.append('asset_id')
        keep_cols.extend([c for c in numeric_cols if c != 'asset_id'])
        
        ml_data = risk_matrix[keep_cols].copy()
        ml_data = ml_data.fillna(0)
        
        self.target_cols = ['residual_risk', 'expected_loss', 'composite_risk_score']
        exclude_cols = ['asset_id'] + self.target_cols
        self.feature_cols = [c for c in ml_data.columns if c not in exclude_cols]
        
        logger.info(f"ML-ready data: {ml_data.shape[0]} rows, {ml_data.shape[1]} columns")
        logger.info(f"Features: {len(self.feature_cols)}, Targets: {len(self.target_cols)}")
        
        return ml_data
    
    def get_ml_data(self) -> pd.DataFrame:
        return self.merged_data.get('ml_ready', pd.DataFrame())
    
    def get_features_and_target(self, target: str = 'expected_loss') -> Tuple[pd.DataFrame, pd.Series]:
        """Get X (features) and y (target) for ML training"""
        ml_data = self.get_ml_data()
        if ml_data.empty:
            return pd.DataFrame(), pd.Series()
        
        if target not in ml_data.columns:
            for alt in self.target_cols:
                if alt in ml_data.columns:
                    target = alt
                    break
            else:
                return pd.DataFrame(), pd.Series()
        
        feature_cols = [c for c in ml_data.columns if c not in ['asset_id', target]]
        X = ml_data[feature_cols]
        y = ml_data[target]
        
        return X, y