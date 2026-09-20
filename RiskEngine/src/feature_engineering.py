"""
Feature Engineering - FIXED: No Data Leakage
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, mutual_info_regression
from sklearn.model_selection import train_test_split
import warnings
import logging
from pathlib import Path
import sys

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature Engineering - NO DATA LEAKAGE"""
    
    def __init__(self, merged_data: Dict[str, pd.DataFrame]):
        self.merged_data = merged_data
        self.feature_sets = {}
        self.scaler = None
        self.selector = None
        self.selected_features = []
        self.feature_importance = None
        self.target_cols = ['expected_loss', 'residual_risk', 'inherent_risk', 'composite_risk_score']
        
        # Store train/test split results
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.X_train_scaled = None
        self.X_test_scaled = None
        self.X_train_selected = None
        self.X_test_selected = None
        
        self.crit_map = {
            'Critical': 5, 'High': 4, 'Medium': 3, 'Low': 2, 'Very Low': 1
        }
    
    def engineer_all_features(self, scale: bool = True, select: bool = True, 
                              test_size: float = 0.2, random_state: int = 42) -> Dict[str, pd.DataFrame]:
        """Create features with PROPER train/test split - NO LEAKAGE"""
        logger.info(" Creating features for ML...")
        
        risk_matrix = self.merged_data.get('risk_matrix', pd.DataFrame())
        
        if risk_matrix.empty:
            logger.error(" risk_matrix not found!")
            return {}
        
        # Create unified features
        unified_df = self._create_unified_features(risk_matrix)
        self.feature_sets['unified'] = unified_df
        
        if unified_df.empty:
            return {}
        
        # Get features and target
        X, y = self._get_features_and_target_from_df(unified_df)
        
        # =====================================================================
        # SPLIT BEFORE ANY SCALING OR SELECTION
        # =====================================================================
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        
        logger.info(f"  Train: {self.X_train.shape[0]} samples, Test: {self.X_test.shape[0]} samples")
        
        # =====================================================================
        # SCALE - FIT ONLY ON TRAINING DATA
        # =====================================================================
        if scale:
            self.scaler = StandardScaler()
            self.X_train_scaled = self.scaler.fit_transform(self.X_train)  # ✅ FIT ON TRAIN ONLY
            self.X_test_scaled = self.scaler.transform(self.X_test)        # ✅ TRANSFORM TEST
        
        # =====================================================================
        # FEATURE SELECTION - FIT ONLY ON TRAINING DATA
        # =====================================================================
        if select and self.X_train_scaled is not None:
            self.X_train_selected, self.X_test_selected, self.selected_features = self._select_features(
                self.X_train_scaled, self.y_train, self.X_test_scaled
            )
            
            # Create feature sets
            train_df = pd.DataFrame(self.X_train_selected, columns=self.selected_features)
            train_df['target'] = self.y_train.values
            
            test_df = pd.DataFrame(self.X_test_selected, columns=self.selected_features)
            test_df['target'] = self.y_test.values
            
            self.feature_sets['train'] = train_df
            self.feature_sets['test'] = test_df
            self.feature_sets['selected'] = train_df
        
        logger.info(f" Created {len(self.feature_sets)} feature sets")
        return self.feature_sets
    
    def _create_unified_features(self, risk_matrix: pd.DataFrame) -> pd.DataFrame:
        """Create unified feature matrix from risk matrix"""
        logger.info("  Creating unified features...")
        
        df = risk_matrix.copy()
        
        if 'asset_id' not in df.columns:
            df['asset_id'] = range(len(df))
        
        # Convert criticality to numeric
        if 'asset_criticality' in df.columns:
            if df['asset_criticality'].dtype == 'object':
                df['asset_criticality'] = df['asset_criticality'].map(self.crit_map).fillna(3)
            df['asset_criticality'] = pd.to_numeric(df['asset_criticality'], errors='coerce').fillna(3)
        
        if 'composite_risk_score' in df.columns:
            df['composite_risk_score'] = pd.to_numeric(df['composite_risk_score'], errors='coerce').fillna(0.5)
        
        if 'criticality_composite' in df.columns:
            df['criticality_composite'] = pd.to_numeric(df['criticality_composite'], errors='coerce').fillna(3)
        
        if 'avg_control_effectiveness' in df.columns:
            df['avg_control_effectiveness'] = pd.to_numeric(df['avg_control_effectiveness'], errors='coerce').fillna(0.5)
        
        # Convert all numeric columns
        numeric_cols = ['vuln_count', 'avg_cvss', 'max_cvss', 'avg_epss', 'avg_days_open',
                       'critical_vuln_count', 'effectiveness_score', 'estimated_total_impact',
                       'inherent_risk', 'residual_risk', 'expected_loss', 'control_effectiveness',
                       'composite_risk_score', 'criticality_composite', 'avg_control_effectiveness',
                       'risk_reduction_potential', 'risk_reduction_ratio']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Create derived features
        if 'vuln_count' in df.columns and 'asset_criticality' in df.columns:
            df['vuln_density'] = df['vuln_count'] / (df['asset_criticality'] + 1)
        
        if 'inherent_risk' in df.columns and 'residual_risk' in df.columns:
            df['risk_reduction'] = df['inherent_risk'] - df['residual_risk']
            df['risk_reduction_ratio'] = df['residual_risk'] / (df['inherent_risk'] + 0.001)
        
        if 'estimated_total_impact' in df.columns and 'residual_risk' in df.columns:
            df['financial_risk'] = df['estimated_total_impact'] * df['residual_risk']
        
        if 'avg_cvss' in df.columns and 'avg_epss' in df.columns:
            df['threat_score'] = (df['avg_cvss'] / 10) * (df['avg_epss'] + 0.1)
        
        if 'avg_days_open' in df.columns:
            df['days_open_normalized'] = df['avg_days_open'] / 365
        
        if 'composite_risk_score' in df.columns:
            df['risk_score_normalized'] = df['composite_risk_score']
        
        # Keep only numeric columns
        numeric_cols_final = df.select_dtypes(include=[np.number]).columns.tolist()
        
        keep_cols = ['asset_id']
        for col in numeric_cols_final:
            if col != 'asset_id':
                keep_cols.append(col)
        for target in self.target_cols:
            if target in df.columns and target not in keep_cols:
                keep_cols.append(target)
        
        unified = df[keep_cols].copy()
        unified = unified.fillna(0)
        
        logger.info(f"     Unified features: {unified.shape}")
        return unified
    
    def _get_features_and_target_from_df(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Get X and y from DataFrame"""
        target = None
        for col in self.target_cols:
            if col in df.columns:
                target = col
                break
        
        if target is None:
            logger.warning("    ⚠ No target found, using first numeric column")
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) > 1:
                target = numeric_cols[1]
            else:
                return pd.DataFrame(), pd.Series()
        
        feature_cols = [c for c in df.columns if c not in ['asset_id', target]]
        X = df[feature_cols]
        y = df[target]
        
        return X, y
    
    def _select_features(self, X_train, y_train, X_test, k: int = 15) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Select features - FIT ONLY ON TRAINING DATA"""
        logger.info("  Selecting features on training data only...")
        
        try:
            # Get feature names
            if hasattr(X_train, 'columns'):
                feature_cols = X_train.columns.tolist()
            else:
                feature_cols = [f'feature_{i}' for i in range(X_train.shape[1])]
            
            if X_train.shape[1] > 1:
                k = min(k, X_train.shape[1])
                self.selector = SelectKBest(score_func=mutual_info_regression, k=k)
                self.selector.fit(X_train, y_train)  # ✅ FIT ON TRAIN ONLY
                
                selected_mask = self.selector.get_support()
                selected_features = [feature_cols[i] for i in range(len(feature_cols)) if selected_mask[i]]
                
                X_train_selected = self.selector.transform(X_train)
                X_test_selected = self.selector.transform(X_test)
                
                self.selected_features = selected_features
                self.feature_importance = pd.DataFrame({
                    'feature': feature_cols,
                    'score': self.selector.scores_
                }).sort_values('score', ascending=False)
                
                logger.info(f"     Selected {len(selected_features)} features")
                return X_train_selected, X_test_selected, selected_features
            else:
                return X_train, X_test, feature_cols
                
        except Exception as e:
            logger.warning(f"    ⚠ Feature selection failed: {e}")
            return X_train, X_test, []
    
    def get_feature_matrix(self, scaled: bool = True, selected: bool = True) -> pd.DataFrame:
        """Get feature matrix - returns training data only (NO LEAKAGE)"""
        if selected and self.feature_sets.get('selected') is not None:
            return self.feature_sets['selected']
        elif scaled and self.feature_sets.get('scaled') is not None:
            return self.feature_sets['scaled']
        else:
            return self.feature_sets.get('unified', pd.DataFrame())
    
    def get_train_test_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get train/test data - NO LEAKAGE"""
        return self.X_train_scaled, self.X_test_scaled, self.y_train, self.y_test
    
    def get_train_test_data_selected(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get selected train/test data - NO LEAKAGE"""
        return self.X_train_selected, self.X_test_selected, self.y_train, self.y_test
    
    def get_features_and_target(self, target: str = 'expected_loss') -> Tuple[pd.DataFrame, pd.Series]:
        """Get X and y for training - returns training data only (NO LEAKAGE)"""
        if self.X_train is not None and self.y_train is not None:
            return self.X_train, self.y_train
        return pd.DataFrame(), pd.Series()
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance scores"""
        return self.feature_importance
    
    def get_feature_names(self) -> List[str]:
        """Get selected feature names"""
        if self.selected_features:
            return self.selected_features
        return []
    
    def transform_test(self, X_test: pd.DataFrame) -> np.ndarray:
        """Transform test data using fitted scaler and selector - NO LEAKAGE"""
        if self.scaler is None:
            raise ValueError("Scaler not fitted yet!")
        
        X_test_scaled = self.scaler.transform(X_test)
        
        if self.selector is not None:
            return self.selector.transform(X_test_scaled)
        
        return X_test_scaled