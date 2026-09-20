"""
Data Preprocessing 
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from typing import Dict, Optional, List, Tuple
import warnings
import logging
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class DataPreprocessor: 
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.encoders = {}
        self.scalers = {}
        self.imputers = {}
        self.feature_columns = {}
        self.preprocessing_stats = {}
        self.imputation_stats = {}  
    def preprocess_all(self) -> Dict[str, pd.DataFrame]: 
        print("\n" + "="*60)
        print("PREPROCESSING & ENRICHMENT")
        print("="*60)
        
        for name, df in self.data.items():
            if df is not None and not df.empty:
                original_shape = df.shape
                self.data[name], stats = self._preprocess_table_with_stats(df, name)
                self.imputation_stats[name] = stats
                print(f"✓ Preprocessed {name}: {original_shape} → {self.data[name].shape}")
                self.preprocessing_stats[name] = {
                    'original_rows': original_shape[0],
                    'original_cols': original_shape[1],
                    'final_rows': self.data[name].shape[0],
                    'final_cols': self.data[name].shape[1]
                }
         
        self._enrich_epss()
        self._enrich_threat_intelligence()
        self._add_asset_criticality()
        self._create_risk_scenarios()
        self.create_asset_risk_features()
        
        print("\n✅ Preprocessing complete!")
        return self.data
    
    def _preprocess_table_with_stats(self, df: pd.DataFrame, name: str) -> Tuple[pd.DataFrame, Dict]:
       
        df = df.copy()
        stats = {}
         
        df = df.drop_duplicates()
         
        df, stats = self._handle_missing_with_stats(df)
         
        df = self._convert_dtypes(df)
         
        df = self._encode_categorical(df, name)
        
        return df, stats
    
    def _handle_missing_with_stats(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
       
        stats = {}
        
        for col in df.columns:
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                missing_pct = missing_count / len(df) * 100
                
                if missing_pct > 80:
                    df = df.drop(columns=[col])
                    stats[col] = 'dropped'
                    continue
                
                if df[col].dtype in ['int64', 'float64']:
                    skew = df[col].skew() if not df[col].isnull().all() else 0
                    if abs(skew) > 1:
                        fill_value = df[col].median() if not df[col].isnull().all() else 0
                    else:
                        fill_value = df[col].mean() if not df[col].isnull().all() else 0
                    stats[col] = fill_value
                    df[col] = df[col].fillna(fill_value)
                else:
                    if missing_pct < 30:
                        mode_val = df[col].mode()
                        fill_value = mode_val[0] if not mode_val.empty else 'Unknown'
                    else:
                        fill_value = 'Unknown'
                    stats[col] = fill_value
                    df[col] = df[col].fillna(fill_value)
        
        return df, stats
    
    def _convert_dtypes(self, df: pd.DataFrame) -> pd.DataFrame: 
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    bool_map = {
                        'True': True, 'False': False,
                        'true': True, 'false': False,
                        'TRUE': True, 'FALSE': False,
                        'Yes': True, 'No': False,
                        'yes': True, 'no': False,
                        'Y': True, 'N': False,
                        '1': True, '0': False
                    }
                    unique_vals = set(df[col].dropna().unique())
                    if unique_vals.issubset(set(bool_map.keys()) | {True, False}):
                        df[col] = df[col].map(bool_map)
                        df[col] = df[col].astype('boolean')
                    else:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass
        
        for col in df.columns:
            if df[col].dtype == 'boolean':
                df[col] = df[col].astype(int)
        
        return df
    
    def _encode_categorical(self, df: pd.DataFrame, name: str) -> pd.DataFrame: 
        for col in df.select_dtypes(include=['object', 'category']).columns:
            if col.lower() in ['id', 'asset_id', 'vuln_id', 'incident_id', 'control_id']:
                continue
            
            if df[col].nunique() > 100:
                continue
            
            if col not in self.encoders:
                self.encoders[col] = LabelEncoder()
                all_values = df[col].astype(str).unique()
                self.encoders[col].fit(all_values)
            
            def encode_value(val):
                val_str = str(val)
                if val_str in self.encoders[col].classes_:
                    return self.encoders[col].transform([val_str])[0]
                return len(self.encoders[col].classes_)
            
            df[col + '_encoded'] = df[col].apply(encode_value)
            df[col + '_encoded'] = df[col + '_encoded'].astype(float)
        
        return df
    
    def _enrich_epss(self): 
        vuln = self.data.get('vulnerabilities')
        if vuln is not None and not vuln.empty:
            if 'exploitability_score' in vuln.columns and 'exploit_available' in vuln.columns:
                vuln['epss_score'] = (
                    vuln['exploitability_score'].fillna(0) / 10.0 * 0.6 +
                    vuln['exploit_available'].fillna(0).astype(int) * 0.3 +
                    vuln.get('known_exploited', 0).fillna(0).astype(int) * 0.1
                )
                vuln['epss_score'] = vuln['epss_score'].clip(0, 1)
            elif 'cvss_score' in vuln.columns:
                vuln['epss_score'] = (vuln['cvss_score'].fillna(0) / 10.0) * 0.6 + 0.1
                vuln['epss_score'] = vuln['epss_score'].clip(0, 1)
            else:
                vuln['epss_score'] = 0.3
            
            self.data['vulnerabilities'] = vuln
            print(f"✓ Enriched {len(vuln):,} vulnerabilities with EPSS scores")
    
    def _enrich_threat_intelligence(self): 
        threat = self.data.get('threat_intelligence')
        vuln = self.data.get('vulnerabilities')
        
        if threat is not None and not threat.empty and vuln is not None:
            if 'cve_id' in threat.columns and 'cve_id' in vuln.columns:
                vuln = vuln.merge(
                    threat[['cve_id', 'severity', 'exploit_available', 'known_exploited']],
                    on='cve_id',
                    how='left',
                    suffixes=('', '_threat')
                )
                for col in ['severity_threat', 'exploit_available_threat', 'known_exploited_threat']:
                    if col in vuln.columns:
                        vuln[col] = vuln[col].fillna(0)
                self.data['vulnerabilities'] = vuln
                print(f"✓ Enriched vulnerabilities with threat intelligence")
    
    def _add_asset_criticality(self): 
        assets = self.data.get('assets')
        if assets is not None and not assets.empty:
            weight = 0
            criticality = pd.Series(0, index=assets.index)
            
            if 'confidentiality_score' in assets.columns:
                criticality += assets['confidentiality_score'].fillna(0) * 0.3
                weight += 0.3
            
            if 'integrity_score' in assets.columns:
                criticality += assets['integrity_score'].fillna(0) * 0.3
                weight += 0.3
            
            if 'availability_score' in assets.columns:
                criticality += assets['availability_score'].fillna(0) * 0.2
                weight += 0.2
            
            if 'revenue_dependency' in assets.columns:
                criticality += assets['revenue_dependency'].fillna(0) * 0.1
                weight += 0.1
            
            if 'regulatory_dependency' in assets.columns:
                criticality += assets['regulatory_dependency'].fillna(0) * 0.1
                weight += 0.1
            
            if weight > 0:
                assets['criticality_composite'] = criticality / weight
            else:
                if 'asset_type' in assets.columns:
                    crit_map = {'Critical': 5, 'High': 4, 'Medium': 3, 'Low': 2, 'Very Low': 1}
                    assets['criticality_composite'] = assets['asset_type'].map(crit_map).fillna(3)
                else:
                    assets['criticality_composite'] = 3
            
            assets['criticality_composite'] = assets['criticality_composite'].clip(1, 5)
            
            self.data['assets'] = assets
            print(f"✓ Added criticality scores to {len(assets):,} assets")
    
    def _create_risk_scenarios(self): 
        scenarios = {
            'data_breach': {
                'description': 'Unauthorized access to sensitive data',
                'impact_multiplier': 1.5,
                'probability_base': 0.3
            },
            'ransomware': {
                'description': 'Ransomware encryption of critical systems',
                'impact_multiplier': 1.8,
                'probability_base': 0.25
            },
            'phishing': {
                'description': 'Phishing attack leading to credential compromise',
                'impact_multiplier': 0.8,
                'probability_base': 0.4
            },
            'ddos': {
                'description': 'Distributed denial of service attack',
                'impact_multiplier': 0.6,
                'probability_base': 0.2
            },
            'insider_threat': {
                'description': 'Malicious insider activity',
                'impact_multiplier': 1.2,
                'probability_base': 0.15
            }
        }
        
        self.risk_scenarios = scenarios
        print(f"✓ Created {len(scenarios)} risk scenarios")
    
    def create_asset_risk_features(self) -> pd.DataFrame: 
        print("\n" + "-"*40)
        print("🔧 CREATING ASSET RISK FEATURES")
        print("-"*40)
        
        assets = self.data.get('assets')
        vuln = self.data.get('vulnerabilities')
        impact = self.data.get('business_impact')
        controls = self.data.get('security_controls')
        
        if assets is None or assets.empty:
            print("⚠ No assets data available")
            return pd.DataFrame()
        
        asset_features = assets.copy()
         
        if vuln is not None and not vuln.empty and 'asset_id' in vuln.columns:
            agg_dict = {}
            numeric_cols = ['cvss_score', 'epss_score', 'exploitability_score']
            for col in numeric_cols:
                if col in vuln.columns:
                    agg_dict[col] = ['mean', 'max', 'std']
            
            if 'severity' in vuln.columns:
                vuln['is_critical'] = vuln['severity'].apply(
                    lambda x: 1 if x in ['Critical', 'critical', 'High', 'high'] else 0
                )
                agg_dict['is_critical'] = 'sum'
            
            if 'patch_available' in vuln.columns:
                agg_dict['patch_available'] = ['sum', 'mean']
            
            if 'exploit_available' in vuln.columns:
                agg_dict['exploit_available'] = 'sum'
            
            vuln_count = vuln.groupby('asset_id').size().reset_index(name='vuln_count')
            
            if agg_dict:
                vuln_agg = vuln.groupby('asset_id').agg(agg_dict).reset_index()
                vuln_agg.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col
                                   for col in vuln_agg.columns.values]
                asset_features = asset_features.merge(vuln_agg, on='asset_id', how='left')
            
            asset_features = asset_features.merge(vuln_count, on='asset_id', how='left')
            
            for col in asset_features.columns:
                if asset_features[col].dtype in ['float64', 'int64']:
                    asset_features[col] = asset_features[col].fillna(0)
         
        if impact is not None and not impact.empty and 'asset_id' in impact.columns:
            impact_cols = ['estimated_total_impact', 'downtime_cost_per_hour', 'revenue_per_hour']
            impact_cols = [c for c in impact_cols if c in impact.columns]
            
            if impact_cols:
                impact_agg = impact.groupby('asset_id')[impact_cols].mean().reset_index()
                asset_features = asset_features.merge(impact_agg, on='asset_id', how='left')
                for col in impact_cols:
                    if col in asset_features.columns:
                        asset_features[col] = asset_features[col].fillna(0)
         
        if controls is not None and not controls.empty:
            control_features = controls.copy()
            if 'asset_id' in control_features.columns and 'effectiveness_score' in control_features.columns:
                ctrl_agg = control_features.groupby('asset_id')['effectiveness_score'].mean().reset_index()
                ctrl_agg.columns = ['asset_id', 'avg_control_effectiveness']
                asset_features = asset_features.merge(ctrl_agg, on='asset_id', how='left')
                asset_features['avg_control_effectiveness'] = asset_features['avg_control_effectiveness'].fillna(0.5)
         
        risk_components = []
        weights = []
        
        if 'cvss_mean' in asset_features.columns:
            asset_features['cvss_mean'] = asset_features['cvss_mean'].fillna(0)
            risk_components.append(asset_features['cvss_mean'] / 10)
            weights.append(0.25)
        
        if 'vuln_count' in asset_features.columns:
            asset_features['vuln_count'] = asset_features['vuln_count'].fillna(0)
            risk_components.append(np.minimum(asset_features['vuln_count'] / 20, 1))
            weights.append(0.15)
        
        if 'criticality_composite' in asset_features.columns:
            asset_features['criticality_composite'] = asset_features['criticality_composite'].fillna(3)
            risk_components.append(asset_features['criticality_composite'] / 5)
            weights.append(0.25)
        
        if 'avg_control_effectiveness' in asset_features.columns:
            asset_features['avg_control_effectiveness'] = asset_features['avg_control_effectiveness'].fillna(0.5)
            risk_components.append(1 - asset_features['avg_control_effectiveness'])
            weights.append(0.20)
        
        if 'estimated_total_impact' in asset_features.columns:
            asset_features['estimated_total_impact'] = asset_features['estimated_total_impact'].fillna(0)
            max_impact = asset_features['estimated_total_impact'].max() or 1
            risk_components.append(np.minimum(asset_features['estimated_total_impact'] / max_impact, 1))
            weights.append(0.15)
        
        if risk_components:
            weights = np.array(weights) / sum(weights)
            asset_features['composite_risk_score'] = sum(c * w for c, w in zip(risk_components, weights))
            asset_features['composite_risk_score'] = asset_features['composite_risk_score'].clip(0, 1)
        
        asset_features = asset_features.fillna(0)
        
        self.data['asset_risk_features'] = asset_features
        print(f"✓ Created asset risk features: {asset_features.shape}")
        
        return asset_features
    
    def get_imputation_stats(self) -> Dict: 
        return self.imputation_stats
    
    def get_data(self) -> Dict[str, pd.DataFrame]: 
        return self.data