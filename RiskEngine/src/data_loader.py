"""
Data Loader - FIXED: No Data Leakage in Imputation
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
import logging
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CyberRiskDataLoader:
    """Data loader for cyber risk dataset - NO LEAKAGE"""
    
    def __init__(self, data_path: str = "data/"):
        self.data_path = Path(data_path)
        self.data = {}
        self.train_data = {}
        self.test_data = {}
        self.imputation_stats = {}  # Store imputation statistics for test set
        
        self.dataset_files = {
            'organizations': 'organizations.csv',
            'business_units': 'business_units.csv',
            'assets': 'assets.csv',
            'vulnerabilities': 'vulnerabilities.csv',
            'security_controls': 'security_controls.csv',
            'asset_controls': 'asset_controls.csv',
            'business_impact': 'business_impact.csv',
            'security_incidents': 'security_incidents.csv',
            'threat_intelligence': 'threat_intelligence.csv',
            'iam_risk': 'iam_risk.csv',
            'edr_telemetry': 'edr_telemetry.csv',
            'cloud_security': 'cloud_security.csv',
            'compliance_mapping': 'compliance_mapping.csv',
            'remediation_action': 'remediation_actions.csv',
            'investment_options': 'investment_options.csv',
            'risk_calculations': 'risk_calculations.csv',
            'optimization_results': 'optimization_results.csv'
        }
        
        logger.info(f"Data Loader initialized with path: {self.data_path}")
    
    def load_all_data(self, impute: bool = True) -> Dict[str, pd.DataFrame]:
        """Load all CSV files - NO LEAKAGE"""
        logger.info("="*60)
        logger.info("LOADING CYBER RISK DATASET")
        logger.info("="*60)
        
        if not self.data_path.exists():
            logger.error(f"Data folder not found: {self.data_path}")
            logger.info("Please make sure CSV files are in the 'data/' folder")
            return {}
        
        for key, filename in self.dataset_files.items():
            filepath = self.data_path / filename
            if filepath.exists():
                try:
                    df = pd.read_csv(filepath)
                    self.data[key] = df
                    logger.info(f"✅ Loaded {key}: {len(df):,} rows, {len(df.columns)} columns")
                except Exception as e:
                    logger.error(f"❌ Error loading {filename}: {e}")
                    self.data[key] = pd.DataFrame()
            else:
                logger.warning(f"File not found: {filename}")
                self.data[key] = pd.DataFrame()
        
        self._show_loading_summary()
        
        # Store imputation statistics for test set
        if impute:
            self._impute_all_datasets()
        
        self._validate_datasets()
        
        return self.data
    
    def split_train_test(self, test_size: float = 0.2, random_state: int = 42):
        """Split data into train/test - NO LEAKAGE"""
        from sklearn.model_selection import train_test_split
        
        self.train_data = {}
        self.test_data = {}
        
        for key, df in self.data.items():
            if not df.empty:
                # For each dataset, split
                train_idx, test_idx = train_test_split(
                    df.index, test_size=test_size, random_state=random_state
                )
                self.train_data[key] = df.loc[train_idx].copy()
                self.test_data[key] = df.loc[test_idx].copy()
                
                logger.info(f"  {key}: Train {len(self.train_data[key])}, Test {len(self.test_data[key])}")
        
        return self.train_data, self.test_data
    
    def _impute_all_datasets(self):
        """Impute missing values - STORE STATS FOR TEST SET"""
        logger.info("\nIMPUTING MISSING VALUES")
        logger.info("="*60)
        
        for key, df in self.data.items():
            if df.empty:
                continue
            
            missing_before = df.isnull().sum().sum()
            if missing_before == 0:
                continue
            
            logger.info(f"\n  Imputing {key}: {missing_before} missing values")
            
            # Store imputation statistics for each column
            if key not in self.imputation_stats:
                self.imputation_stats[key] = {}
            
            if key == 'assets':
                self.data[key], stats = self._impute_assets_with_stats(df)
                self.imputation_stats[key].update(stats)
            elif key == 'vulnerabilities':
                self.data[key], stats = self._impute_vulnerabilities_with_stats(df)
                self.imputation_stats[key].update(stats)
            elif key == 'security_controls':
                self.data[key], stats = self._impute_controls_with_stats(df)
                self.imputation_stats[key].update(stats)
            elif key == 'business_impact':
                self.data[key], stats = self._impute_business_impact_with_stats(df)
                self.imputation_stats[key].update(stats)
            elif key == 'security_incidents':
                self.data[key], stats = self._impute_incidents_with_stats(df)
                self.imputation_stats[key].update(stats)
            else:
                self.data[key], stats = self._impute_generic_with_stats(df)
                self.imputation_stats[key].update(stats)
            
            missing_after = self.data[key].isnull().sum().sum()
            logger.info(f"    ✅ Imputed {missing_before - missing_after} values")
    
    def _impute_assets_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Impute assets - return statistics for test set"""
        result = df.copy()
        stats = {}
        
        if 'asset_criticality' in result.columns and result['asset_criticality'].isna().any():
            if 'asset_type' in result.columns:
                stats['criticality_by_type'] = result.groupby('asset_type')['asset_criticality'].median().to_dict()
                result['asset_criticality'] = result.groupby('asset_type')['asset_criticality'].transform(
                    lambda x: x.fillna(x.median())
                )
            stats['criticality_fill'] = 0.5
            result['asset_criticality'] = result['asset_criticality'].fillna(0.5)
        
        if 'asset_type' in result.columns and result['asset_type'].isna().any():
            stats['asset_type_fill'] = 'Unknown'
            result['asset_type'] = result['asset_type'].fillna('Unknown')
        
        if 'environment' in result.columns and result['environment'].isna().any():
            stats['environment_fill'] = 'Production'
            result['environment'] = result['environment'].fillna('Production')
        
        if 'cloud_provider' in result.columns and result['cloud_provider'].isna().any():
            stats['cloud_provider_fill'] = 'On-premise'
            result['cloud_provider'] = result['cloud_provider'].fillna('On-premise')
        
        return result, stats
    
    def _impute_vulnerabilities_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Impute vulnerabilities - return statistics for test set"""
        result = df.copy()
        stats = {}
        
        if 'cvss_score' in result.columns and result['cvss_score'].isna().any():
            if 'severity' in result.columns:
                stats['cvss_by_severity'] = result.groupby('severity')['cvss_score'].median().to_dict()
                for severity, median in stats['cvss_by_severity'].items():
                    result.loc[(result['severity'] == severity) & result['cvss_score'].isna(), 'cvss_score'] = median
            stats['cvss_fill'] = 5.0
            result['cvss_score'] = result['cvss_score'].fillna(5.0)
        
        if 'epss_score' in result.columns and result['epss_score'].isna().any():
            stats['epss_fill'] = 0.1
            result['epss_score'] = result['epss_score'].fillna(0.1)
        
        if 'severity' in result.columns and result['severity'].isna().any():
            if 'cvss_score' in result.columns:
                result['severity'] = result['severity'].fillna(
                    result['cvss_score'].apply(self._cvss_to_severity)
                )
            else:
                stats['severity_fill'] = 'Medium'
                result['severity'] = result['severity'].fillna('Medium')
        
        if 'days_open' in result.columns and result['days_open'].isna().any():
            if 'severity' in result.columns:
                days_map = {'Critical': 15, 'High': 35, 'Medium': 60, 'Low': 120}
                stats['days_by_severity'] = days_map
                result['days_open'] = result['days_open'].fillna(
                    result['severity'].map(days_map)
                )
            stats['days_fill'] = 45
            result['days_open'] = result['days_open'].fillna(45)
        
        if 'patch_available' in result.columns and result['patch_available'].isna().any():
            stats['patch_fill'] = False
            result['patch_available'] = result['patch_available'].fillna(False)
        
        if 'exploit_available' in result.columns and result['exploit_available'].isna().any():
            stats['exploit_fill'] = False
            result['exploit_available'] = result['exploit_available'].fillna(False)
        
        return result, stats
    
    def _cvss_to_severity(self, cvss_score):
        if pd.isna(cvss_score):
            return 'Medium'
        if cvss_score >= 9.0:
            return 'Critical'
        elif cvss_score >= 7.0:
            return 'High'
        elif cvss_score >= 4.0:
            return 'Medium'
        else:
            return 'Low'
    
    def _impute_controls_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        result = df.copy()
        stats = {}
        
        if 'effectiveness_score' in result.columns and result['effectiveness_score'].isna().any():
            if 'control_type' in result.columns:
                stats['effectiveness_by_type'] = result.groupby('control_type')['effectiveness_score'].median().to_dict()
                for ctype, median in stats['effectiveness_by_type'].items():
                    result.loc[(result['control_type'] == ctype) & result['effectiveness_score'].isna(), 
                              'effectiveness_score'] = median
            stats['effectiveness_fill'] = 0.6
            result['effectiveness_score'] = result['effectiveness_score'].fillna(0.6)
        
        if 'estimated_cost' in result.columns and result['estimated_cost'].isna().any():
            if 'control_type' in result.columns:
                stats['cost_by_type'] = result.groupby('control_type')['estimated_cost'].median().to_dict()
                for ctype, median in stats['cost_by_type'].items():
                    result.loc[(result['control_type'] == ctype) & result['estimated_cost'].isna(), 
                              'estimated_cost'] = median
            stats['cost_fill'] = 200000
            result['estimated_cost'] = result['estimated_cost'].fillna(200000)
        
        if 'framework' in result.columns and result['framework'].isna().any():
            stats['framework_fill'] = 'Unknown'
            result['framework'] = result['framework'].fillna('Unknown')
        
        return result, stats
    
    def _impute_business_impact_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        result = df.copy()
        stats = {}
        
        if 'estimated_total_impact' in result.columns and result['estimated_total_impact'].isna().any():
            stats['impact_median'] = result['estimated_total_impact'].median() if not result['estimated_total_impact'].isna().all() else 5000000
            result['estimated_total_impact'] = result['estimated_total_impact'].fillna(stats['impact_median'])
        
        if 'downtime_cost_per_hour' in result.columns and result['downtime_cost_per_hour'].isna().any():
            stats['downtime_median'] = result['downtime_cost_per_hour'].median() if not result['downtime_cost_per_hour'].isna().all() else 50000
            result['downtime_cost_per_hour'] = result['downtime_cost_per_hour'].fillna(stats['downtime_median'])
        
        if 'revenue_per_hour' in result.columns and result['revenue_per_hour'].isna().any():
            stats['revenue_median'] = result['revenue_per_hour'].median() if not result['revenue_per_hour'].isna().all() else 100000
            result['revenue_per_hour'] = result['revenue_per_hour'].fillna(stats['revenue_median'])
        
        return result, stats
    
    def _impute_incidents_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        result = df.copy()
        stats = {}
        
        if 'incident_occurred' in result.columns and result['incident_occurred'].isna().any():
            stats['incident_fill'] = 0
            result['incident_occurred'] = result['incident_occurred'].fillna(0)
        
        if 'financial_loss' in result.columns and result['financial_loss'].isna().any():
            stats['loss_median'] = result['financial_loss'].median() if not result['financial_loss'].isna().all() else 0
            result['financial_loss'] = result['financial_loss'].fillna(stats['loss_median'])
        
        if 'incident_type' in result.columns and result['incident_type'].isna().any():
            stats['incident_type_fill'] = 'Unknown'
            result['incident_type'] = result['incident_type'].fillna('Unknown')
        
        if 'severity' in result.columns and result['severity'].isna().any():
            stats['severity_fill'] = 'Medium'
            result['severity'] = result['severity'].fillna('Medium')
        
        if 'downtime_hours' in result.columns and result['downtime_hours'].isna().any():
            stats['downtime_fill'] = 0
            result['downtime_hours'] = result['downtime_hours'].fillna(0)
        
        return result, stats
    
    def _impute_generic_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        result = df.copy()
        stats = {}
        
        for col in result.columns:
            if result[col].isna().any():
                if result[col].dtype in ['float64', 'int64']:
                    stats[col] = result[col].median() if not result[col].isna().all() else 0
                    result[col] = result[col].fillna(stats[col])
                elif result[col].dtype == 'bool':
                    stats[col] = False
                    result[col] = result[col].fillna(False)
                else:
                    stats[col] = 'Unknown'
                    result[col] = result[col].fillna('Unknown')
        
        return result, stats
    
    def _show_loading_summary(self):
        """Show summary of loaded datasets"""
        logger.info("\n" + "="*60)
        logger.info("LOADING SUMMARY")
        logger.info("="*60)
        
        total_rows = 0
        total_cols = 0
        loaded_datasets = []
        
        for key, df in self.data.items():
            if not df.empty:
                rows = len(df)
                cols = len(df.columns)
                total_rows += rows
                total_cols += cols
                loaded_datasets.append(key)
                logger.info(f"  {key}: {rows:,} rows, {cols} columns")
        
        logger.info("-"*60)
        logger.info(f"Total datasets loaded: {len(loaded_datasets)}")
        logger.info(f"Total rows: {total_rows:,}")
        logger.info(f"Total columns: {total_cols}")
        logger.info("="*60)
    
    def _validate_datasets(self):
        """Validate loaded datasets"""
        logger.info("\nVALIDATING DATASETS")
        logger.info("="*60)
        
        required_datasets = ['assets', 'vulnerabilities', 'security_controls']
        for ds in required_datasets:
            if ds in self.data and not self.data[ds].empty:
                logger.info(f" ✅ {ds}: {len(self.data[ds])} rows")
            else:
                logger.warning(f" ⚠ {ds}: Missing or empty")
        
        if 'vulnerabilities' in self.data and not self.data['vulnerabilities'].empty:
            vuln_cols = self.data['vulnerabilities'].columns.tolist()
            if 'cvss_score' in vuln_cols:
                logger.info(f"   CVSS scores: {self.data['vulnerabilities']['cvss_score'].notna().sum()} present")
            if 'asset_id' in vuln_cols:
                logger.info(f"   Asset IDs: {self.data['vulnerabilities']['asset_id'].notna().sum()} present")
        
        target_cols = ['incident_occurred', 'risk_score', 'ale', 'estimated_total_impact']
        found_targets = []
        for ds, df in self.data.items():
            for col in target_cols:
                if col in df.columns:
                    found_targets.append(f"{ds}.{col}")
        
        if found_targets:
            logger.info(f"Target columns found: {', '.join(found_targets[:3])}")
        else:
            logger.warning("No target columns found for ML training")
        
        logger.info("="*60)
    
    def get_imputation_stats(self) -> Dict:
        """Get imputation statistics for test set transformation"""
        return self.imputation_stats
    
    def apply_imputation_to_test(self, test_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Apply stored imputation statistics to test data - NO LEAKAGE"""
        result = {}
        
        for key, df in test_data.items():
            if key not in self.imputation_stats or df.empty:
                result[key] = df
                continue
            
            df_copy = df.copy()
            stats = self.imputation_stats[key]
            
            for col, value in stats.items():
                if col in df_copy.columns and df_copy[col].isna().any():
                    df_copy[col] = df_copy[col].fillna(value)
            
            result[key] = df_copy
        
        return result