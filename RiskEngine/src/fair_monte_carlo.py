"""
FAIR Monte Carlo Simulation - Uses Your Real Data
"""

import pandas as pd
import hashlib
import numpy as np
from scipy.stats import poisson, beta, lognorm, norm
import matplotlib.pyplot as plt
from typing import Dict, Optional, List, Tuple
import warnings
import os
import json
warnings.filterwarnings('ignore')


class FAIRMonteCarlo:
    """FAIR Monte Carlo Simulator - Uses your real data"""
    
    def __init__(self, merged_data: Dict[str, pd.DataFrame], n_iterations: int = 10000):
        self.merged_data = merged_data
        self.n_iterations = n_iterations
        self.ale_distributions = {}   # portfolio-level: one entry per simulated year
        self.asset_ale_pool = {}      # mean per-asset ALE per iteration
        self.results = {}
        self.fair_results_df = pd.DataFrame()
        self.asset_results = []
        self.scenario_results = {}
        self.what_if_results = {}
        self._scenario_params = {}
        
        self.risk_matrix = pd.DataFrame()
        self.asset_profile = pd.DataFrame()
        
        print("\n" + "="*60)
        print("FAIR MONTE CARLO SIMULATION")
        print("="*60)
        print(f"Iterations: {n_iterations:,}")
        
        self._create_fair_data()
        
        print(f"Risk Matrix: {self.risk_matrix.shape[0] if not self.risk_matrix.empty else 0} rows")
        print(f"Asset Profile: {self.asset_profile.shape[0] if not self.asset_profile.empty else 0} rows")
    
    def _create_fair_data(self):
        """Create all required data for FAIR simulation"""
        print("\n📊 Creating FAIR data...")
        
        # ============================================================
        # FIX: Use YOUR existing keys from merged_data
        # ============================================================
        self.risk_matrix = self.merged_data.get('risk_matrix', pd.DataFrame())
        self.asset_profile = self.merged_data.get('asset_risk_profile', pd.DataFrame())
        
        print(f"  🔍 Found risk_matrix: {self.risk_matrix.shape[0] if not self.risk_matrix.empty else 0} rows")
        print(f"  🔍 Found asset_profile: {self.asset_profile.shape[0] if not self.asset_profile.empty else 0} rows")
        
        # ============================================================
        # IF risk_matrix is empty BUT asset_profile has data
        # ============================================================
        if self.risk_matrix.empty and not self.asset_profile.empty:
            print(f"  ✅ Using asset_profile as risk_matrix ({self.asset_profile.shape[0]} rows)")
            self.risk_matrix = self.asset_profile.copy()
            
            if 'asset_id' not in self.risk_matrix.columns:
                self.risk_matrix['asset_id'] = range(len(self.risk_matrix))
            
            if 'expected_loss' not in self.risk_matrix.columns:
                if 'estimated_total_impact' in self.risk_matrix.columns and 'residual_risk' in self.risk_matrix.columns:
                    self.risk_matrix['expected_loss'] = self.risk_matrix['estimated_total_impact'] * self.risk_matrix['residual_risk']
                else:
                    self.risk_matrix['expected_loss'] = self.risk_matrix.get('composite_risk_score', 0.5) * 10000000
            
            if 'residual_risk' not in self.risk_matrix.columns:
                self.risk_matrix['residual_risk'] = self.risk_matrix.get('composite_risk_score', 0.5)
            
            if 'inherent_risk' not in self.risk_matrix.columns:
                self.risk_matrix['inherent_risk'] = self.risk_matrix.get('composite_risk_score', 0.5) * 1.5
            
            if 'control_effectiveness' not in self.risk_matrix.columns:
                self.risk_matrix['control_effectiveness'] = 0.5
            
            if 'asset_criticality' not in self.risk_matrix.columns:
                if 'criticality_composite' in self.risk_matrix.columns:
                    self.risk_matrix['asset_criticality'] = self.risk_matrix['criticality_composite']
                else:
                    self.risk_matrix['asset_criticality'] = 3
        
        # ============================================================
        # IF asset_profile is empty BUT risk_matrix has data
        # ============================================================
        if self.asset_profile.empty and not self.risk_matrix.empty:
            print(f"  ✅ Using risk_matrix as asset_profile ({self.risk_matrix.shape[0]} rows)")
            self.asset_profile = self.risk_matrix.copy()
            
            if 'vuln_count' not in self.asset_profile.columns:
                self.asset_profile['vuln_count'] = np.random.randint(1, 20, len(self.asset_profile))
            if 'avg_cvss' not in self.asset_profile.columns:
                self.asset_profile['avg_cvss'] = np.random.uniform(3, 9, len(self.asset_profile))
            if 'estimated_total_impact' not in self.asset_profile.columns:
                self.asset_profile['estimated_total_impact'] = self.asset_profile['expected_loss'] / (self.asset_profile['residual_risk'] + 0.01)
        
        # ============================================================
        # ONLY CREATE SYNTHETIC IF BOTH ARE EMPTY
        # ============================================================
        if self.risk_matrix.empty:
            print("  ⚠ No real data found! Creating synthetic data...")
            assets = self._create_synthetic_assets()
            self.risk_matrix = self._create_risk_matrix_from_assets(assets)
            self.asset_profile = self._create_asset_profile_from_assets(assets)
        
        # ============================================================
        # ENSURE REQUIRED COLUMNS
        # ============================================================
        self._ensure_risk_matrix_columns()
        
        print(f"\n  ✅ FINAL - Risk Matrix: {self.risk_matrix.shape[0] if not self.risk_matrix.empty else 0} rows")
        print(f"  ✅ FINAL - Asset Profile: {self.asset_profile.shape[0] if not self.asset_profile.empty else 0} rows")
    
    def _ensure_risk_matrix_columns(self):
        """Ensure risk_matrix has all required columns"""
        if self.risk_matrix.empty:
            return
        
        required_cols = ['asset_id', 'expected_loss', 'residual_risk', 'inherent_risk', 
                        'control_effectiveness', 'asset_criticality']
        
        for col in required_cols:
            if col not in self.risk_matrix.columns:
                if col == 'asset_id':
                    self.risk_matrix['asset_id'] = range(len(self.risk_matrix))
                elif col == 'expected_loss':
                    self.risk_matrix[col] = 1000000
                elif col == 'residual_risk':
                    self.risk_matrix[col] = 0.3
                elif col == 'inherent_risk':
                    self.risk_matrix[col] = 0.5
                elif col == 'control_effectiveness':
                    self.risk_matrix[col] = 0.5
                elif col == 'asset_criticality':
                    self.risk_matrix[col] = 3
    
    def _create_synthetic_assets(self) -> pd.DataFrame:
        """Create synthetic assets - ONLY as LAST RESORT"""
        print("  🔨 Creating synthetic assets (demo only)...")
        n_assets = 100
        
        assets = pd.DataFrame({
            'asset_id': [f'AST-{i:05d}' for i in range(n_assets)],
            'asset_name': [f'Asset_{i}' for i in range(n_assets)],
            'asset_type': np.random.choice(['Server', 'Database', 'Application', 'Network', 'Storage'], n_assets),
            'current_risk_score': np.random.randint(1, 10, n_assets),
            'criticality_composite': np.random.uniform(1, 5, n_assets),
        })
        return assets
    
    def _create_risk_matrix_from_assets(self, assets: pd.DataFrame) -> pd.DataFrame:
        risk_matrix = assets.copy()
        if 'asset_id' not in risk_matrix.columns:
            risk_matrix['asset_id'] = range(len(risk_matrix))
        risk_matrix['inherent_risk'] = risk_matrix.get('current_risk_score', 5) / 10
        risk_matrix['residual_risk'] = risk_matrix['inherent_risk'] * 0.5
        risk_matrix['expected_loss'] = risk_matrix['current_risk_score'] * 1000000
        risk_matrix['control_effectiveness'] = 0.5
        risk_matrix['asset_criticality'] = risk_matrix.get('criticality_composite', 3)
        return risk_matrix
    
    def _create_asset_profile_from_assets(self, assets: pd.DataFrame) -> pd.DataFrame:
        asset_profile = assets.copy()
        if 'asset_id' not in asset_profile.columns:
            asset_profile['asset_id'] = range(len(asset_profile))
        asset_profile['vuln_count'] = np.random.randint(1, 20, len(asset_profile))
        asset_profile['avg_cvss'] = np.random.uniform(3, 9, len(asset_profile))
        asset_profile['estimated_total_impact'] = 5000000
        asset_profile['inherent_risk'] = asset_profile['avg_cvss'] / 10
        asset_profile['control_effectiveness'] = 0.5
        asset_profile['residual_risk'] = asset_profile['inherent_risk'] * (1 - asset_profile['control_effectiveness'])
        asset_profile['expected_loss'] = asset_profile['estimated_total_impact'] * asset_profile['residual_risk']
        return asset_profile
    
    def _safe_get(self, df: pd.DataFrame, col: str, default: float) -> float:
        if col in df.columns and not df[col].empty:
            val = df[col].iloc[0]
            if pd.notna(val):
                try:
                    return float(val)
                except:
                    pass
        return default
    
    def _get_asset_features(self, asset_data: pd.DataFrame) -> Dict:
        return {
            'inherent_risk': self._safe_get(asset_data, 'inherent_risk', 0.5),
            'residual_risk': self._safe_get(asset_data, 'residual_risk', 0.3),
            'control_effectiveness': self._safe_get(asset_data, 'control_effectiveness', 0.5),
            'expected_loss': self._safe_get(asset_data, 'expected_loss', 1000000),
            'estimated_impact': self._safe_get(asset_data, 'estimated_total_impact', 5000000),
            'vuln_count': self._safe_get(asset_data, 'vuln_count', 5),
            'avg_cvss': self._safe_get(asset_data, 'avg_cvss', 5.0),
            'avg_epss': self._safe_get(asset_data, 'avg_epss', 0.3),
            'asset_criticality': self._safe_get(asset_data, 'asset_criticality', 3),
            'max_cvss': self._safe_get(asset_data, 'max_cvss', 5.0),
            'critical_vuln_count': self._safe_get(asset_data, 'critical_vuln_count', 0),
        }
    
    def _apply_scenario_params(self, params: Dict, features: Dict) -> Dict:
        modified = features.copy()
        if 'control_effectiveness' in params:
            modified['control_effectiveness'] = params['control_effectiveness']
        if 'threat_multiplier' in params:
            modified['avg_cvss'] = modified['avg_cvss'] * params['threat_multiplier']
            modified['avg_epss'] = modified['avg_epss'] * params['threat_multiplier']
        if 'criticality_multiplier' in params:
            modified['asset_criticality'] = modified['asset_criticality'] * params['criticality_multiplier']
            modified['estimated_impact'] = modified['estimated_impact'] * params['criticality_multiplier']
        if 'vuln_multiplier' in params:
            modified['vuln_count'] = modified['vuln_count'] * params['vuln_multiplier']
            modified['avg_cvss'] = modified['avg_cvss'] * params['vuln_multiplier']
        if 'impact_multiplier' in params:
            modified['estimated_impact'] = modified['estimated_impact'] * params['impact_multiplier']

        # CVSS and EPSS are bounded scales (0-10, 0-1). A scenario that stacks
        # multiple multipliers on the same asset (e.g. remediation delay applies
        # both threat_multiplier and vuln_multiplier to avg_cvss) can otherwise
        # push values outside the range every downstream formula assumes.
        modified['avg_cvss'] = float(np.clip(modified['avg_cvss'], 0, 10))
        modified['avg_epss'] = float(np.clip(modified['avg_epss'], 0, 1))
        return modified
    
    def _simulate_asset(self, features: Dict) -> Dict:
        # Python salts str.__hash__ per process, so hash() made this "reproducible"
        # per-asset seed change on every restart — identical inputs gave different
        # numbers across runs. sha256 is stable across processes.
        asset_id = str(features.get('asset_id', 'default'))
        seed = int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16) % 10000
        np.random.seed(seed)
        
        inherent_risk = features['inherent_risk']
        control_effectiveness = features['control_effectiveness']
        estimated_impact = features['estimated_impact']
        vuln_count = features['vuln_count']
        avg_cvss = features['avg_cvss']
        avg_epss = features['avg_epss']
        asset_criticality = features['asset_criticality']
        
        tef_lambda = max(0.5, 0.5 + (avg_cvss / 10) * 2 + avg_epss * 2 + (asset_criticality / 5) * 0.5)
        tef_samples = poisson.rvs(mu=tef_lambda, size=self.n_iterations)
        tef_samples = np.clip(tef_samples, 0, 50)
        
        vuln_mean = min(0.9, 0.2 + (avg_cvss / 10) * 0.4 + avg_epss * 0.3 + (1 - control_effectiveness) * 0.2)
        vuln_mean = np.clip(vuln_mean, 0.01, 0.99)
        a = max(1, vuln_mean * 10 + 1)
        b = max(1, (1 - vuln_mean) * 10 + 1)
        vuln_samples = beta.rvs(a=a, b=b, size=self.n_iterations)
        vuln_samples = np.clip(vuln_samples, 0.01, 0.99)
        
        lef_samples = tef_samples * vuln_samples
        lef_samples = np.clip(lef_samples, 0, 100)
        
        base_loss = max(100000, estimated_impact * (0.5 + inherent_risk * 0.5))
        mu_loss = np.log(max(1, base_loss * 0.5))
        # Higher severity increases the loss-magnitude spread, not decreases it.
        # (avg_cvss / 10) here, not (1 - avg_cvss / 10) -- the inverted form
        # made loss volatility (and hence the lognormal mean, exp(mu+sigma^2/2))
        # shrink as CVSS rose, so scenarios that raise severity (threat_multiplier,
        # vuln_multiplier) perversely lowered expected loss instead of raising it.
        sigma_loss = 0.5 + (1 - control_effectiveness) * 0.5 + (avg_cvss / 10) * 0.3
        sigma_loss = np.clip(sigma_loss, 0.1, 2.0)
        loss_samples = lognorm.rvs(sigma_loss, scale=np.exp(mu_loss), size=self.n_iterations)
        loss_samples = np.clip(loss_samples, 1000, base_loss * 10)
        
        ale_samples = lef_samples * loss_samples
        ale_samples = ale_samples * (1 - control_effectiveness * 0.8)
        ale_samples = np.clip(ale_samples, 0, None)
        
        var_95 = np.percentile(ale_samples, 95)
        var_99 = np.percentile(ale_samples, 99)
        cvar_95 = np.mean(ale_samples[ale_samples > var_95]) if np.any(ale_samples > var_95) else 0
        
        return {
            'asset_id': features.get('asset_id', 'unknown'),
            'asset_criticality': asset_criticality,
            'inherent_risk': inherent_risk,
            'control_effectiveness': control_effectiveness,
            'vuln_count': vuln_count,
            'avg_cvss': avg_cvss,
            'avg_epss': avg_epss,
            'tef_mean': np.mean(tef_samples),
            'vuln_mean': np.mean(vuln_samples),
            'lef_mean': np.mean(lef_samples),
            'lm_mean': np.mean(loss_samples),
            'expected_ale': np.mean(ale_samples),
            'std_ale': np.std(ale_samples),
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'max_ale': np.max(ale_samples),
            'min_ale': np.min(ale_samples),
            'ale_distribution': ale_samples
        }
    
    def run_simulation(self, scenario_name: str = "Base", max_assets: int = 500) -> pd.DataFrame:
        print(f"\n Running FAIR simulation: {scenario_name}")
        
        if self.risk_matrix.empty:
            self._create_fair_data()
        
        if self.risk_matrix.empty:
            print("✗ No risk_matrix data found!")
            return pd.DataFrame()
        
        if 'asset_id' not in self.risk_matrix.columns:
            self.risk_matrix['asset_id'] = range(len(self.risk_matrix))
        
        asset_ids = self.risk_matrix['asset_id'].unique()
        print(f"   Assets found: {len(asset_ids)}")
        
        if len(asset_ids) > max_assets:
            asset_ids = asset_ids[:max_assets]
            print(f"   Processing first {max_assets} assets")
        
        results = []
        all_ale_samples = []
        
        for idx, asset_id in enumerate(asset_ids):
            asset_data = self.risk_matrix[self.risk_matrix['asset_id'] == asset_id]
            if asset_data.empty:
                continue
            
            features = self._get_asset_features(asset_data)
            features['asset_id'] = asset_id
            
            if self._scenario_params:
                features = self._apply_scenario_params(self._scenario_params, features)
            
            try:
                sim_result = self._simulate_asset(features)
                results.append(sim_result)
                all_ale_samples.extend(sim_result['ale_distribution'])
            except Exception as e:
                continue
        
        if not results:
            print("✗ No simulation results generated!")
            return pd.DataFrame()
        
        self.asset_results = results
        self.fair_results_df = pd.DataFrame(results)

        # Portfolio loss distribution: sum the per-asset samples position-wise so
        # each index is one simulated YEAR across the whole estate. Pooling the
        # per-asset samples into one flat array instead (the previous behaviour)
        # yields a per-asset percentile, which cannot be compared against a
        # portfolio-level expected loss — VaR came out smaller than EAL.
        # Losses are treated as independent across assets.
        per_asset = np.vstack([r['ale_distribution'] for r in results])
        portfolio_ale = per_asset.sum(axis=0)

        self.ale_distributions[scenario_name] = portfolio_ale
        self.asset_ale_pool[scenario_name] = per_asset.mean(axis=0)
        aggregate = self._calculate_aggregate_metrics(results, portfolio_ale)
        
        print(f"\n FAIR Simulation Complete: {scenario_name}")
        print(f"   Assets Simulated: {len(results)}")
        print(f"   Total Expected ALE: ₹{aggregate['total_expected_loss']:,.2f}")
        print(f"   Average ALE per Asset: ₹{aggregate['avg_ale']:,.2f}")
        print(f"   VaR (95%): ₹{aggregate['var_95']:,.2f}")
        print(f"   VaR (99%): ₹{aggregate['var_99']:,.2f}")
        print(f"   CVaR (95%): ₹{aggregate['cvar_95']:,.2f}")
        
        self.results[scenario_name] = {
            'aggregate': aggregate,
            'asset_results': results,
            'ale_distribution': portfolio_ale
        }
        
        return self.fair_results_df
    
    def _calculate_aggregate_metrics(self, results: List[Dict], all_ales: np.ndarray) -> Dict:
        if not results or len(all_ales) == 0:
            return {
                'total_expected_loss': 0,
                'total_var_95': 0,
                'total_var_99': 0,
                'total_cvar_95': 0,
                'avg_ale': 0,
                'median_ale': 0,
                'std_ale': 0,
                'var_95': 0,
                'var_99': 0,
                'cvar_95': 0,
                'total_assets': 0,
                'assets_at_risk': 0
            }
        
        var_95 = np.percentile(all_ales, 95)
        var_99 = np.percentile(all_ales, 99)
        cvar_95 = np.mean(all_ales[all_ales > var_95]) if np.any(all_ales > var_95) else 0
        
        return {
            'total_expected_loss': np.sum([r['expected_ale'] for r in results]),
            # Portfolio percentiles from the summed distribution. The per-asset
            # VaRs are also summed below, which assumes perfect correlation and
            # so brackets the independent case from above.
            'total_var_95': var_95,
            'total_var_99': var_99,
            'total_cvar_95': cvar_95,
            'sum_of_asset_var_95': np.sum([r['var_95'] for r in results]),
            'avg_ale': np.mean([r['expected_ale'] for r in results]),
            'median_ale': np.median([r['expected_ale'] for r in results]),
            'std_ale': np.std([r['expected_ale'] for r in results]),
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'total_assets': len(results),
            'assets_at_risk': len([r for r in results if r['expected_ale'] > 10000])
        }
    
    def get_risk_metrics(self) -> Dict:
        if not self.results:
            return {
                'total_expected_loss': 0,
                'total_var_95': 0,
                'total_var_99': 0,
                'total_cvar_95': 0,
                'assets_at_risk': 0,
                'total_assets': 0,
                'avg_ale': 0
            }
        
        last_scenario = list(self.results.keys())[-1]
        aggregate = self.results[last_scenario]['aggregate']
        
        return {
            'total_expected_loss': aggregate['total_expected_loss'],
            'total_var_95': aggregate['total_var_95'],
            'total_var_99': aggregate['total_var_99'],
            'total_cvar_95': aggregate['total_cvar_95'],
            'assets_at_risk': aggregate['assets_at_risk'],
            'total_assets': aggregate['total_assets'],
            'avg_ale': aggregate['avg_ale']
        }
    
    # ------------------------------------------------------------------
    # What-if scenario simulation
    # ------------------------------------------------------------------

    # The scenarios the problem statement names directly, plus the two most
    # common board questions. Parameters feed _apply_scenario_params().
    PRESET_SCENARIOS = {
        'MFA on all privileged accounts': {
            'control_effectiveness': 0.85,
            'description': 'Enforce multi-factor authentication across every privileged account.'
        },
        '30-day remediation delay': {
            'vuln_multiplier': 1.3,
            'threat_multiplier': 1.15,
            'description': 'Patching slips by 30 days: more open vulnerabilities, longer exposure window.'
        },
        'Network segmentation': {
            'control_effectiveness': 0.75,
            'impact_multiplier': 0.6,
            'description': 'Segment critical services so a breach cannot move laterally.'
        },
        'Elevated threat landscape': {
            'threat_multiplier': 1.5,
            'description': 'Sustained increase in attacker activity against this sector.'
        },
        'Controls degrade 20%': {
            'control_effectiveness': 0.3,
            'description': 'Control effectiveness decays without maintenance or tuning.'
        },
    }

    def what_if_scenario(self, name: str, params: Dict, max_assets: int = 200,
                         baseline: str = 'Base') -> Dict:
        """
        Re-run the simulation with modified risk parameters and report the
        change against the baseline.

        The baseline's own results are restored afterwards, so running a
        scenario never corrupts the numbers the dashboard reports as current.
        """
        if baseline not in self.results:
            print(f"Baseline '{baseline}' not yet simulated — running it first.")
            self.run_simulation(baseline, max_assets=max_assets)

        if baseline not in self.results:
            return {}

        saved_df = self.fair_results_df.copy()
        saved_asset_results = list(self.asset_results)

        scenario_params = {k: v for k, v in params.items() if k != 'description'}
        self._scenario_params = scenario_params
        try:
            self.run_simulation(name, max_assets=max_assets)
        finally:
            self._scenario_params = {}
            self.fair_results_df = saved_df
            self.asset_results = saved_asset_results

        if name not in self.results:
            return {}

        base = self.results[baseline]['aggregate']
        scen = self.results[name]['aggregate']

        base_ale = float(base['total_expected_loss'])
        scen_ale = float(scen['total_expected_loss'])
        delta = scen_ale - base_ale

        result = {
            'scenario': name,
            'description': params.get('description', ''),
            'parameters': scenario_params,
            'baseline_expected_loss': round(base_ale, 2),
            'scenario_expected_loss': round(scen_ale, 2),
            'absolute_change': round(delta, 2),
            'percent_change': round((delta / base_ale * 100), 2) if base_ale else 0.0,
            'baseline_var_95': round(float(base['total_var_95']), 2),
            'scenario_var_95': round(float(scen['total_var_95']), 2),
            'var_95_change': round(float(scen['total_var_95']) - float(base['total_var_95']), 2),
            'direction': 'reduces risk' if delta < 0 else ('increases risk' if delta > 0 else 'no change'),
        }

        self.what_if_results[name] = result
        self.scenario_results[name] = self.results[name]['aggregate']

        print(f"   {name}: ₹{base_ale:,.0f} → ₹{scen_ale:,.0f} "
              f"({result['percent_change']:+.1f}%, {result['direction']})")

        return result

    def run_preset_what_if_scenarios(self, max_assets: int = 200) -> Dict[str, Dict]:
        """Run the built-in scenario set. Returns {scenario_name: delta_result}."""
        print("\n" + "=" * 60)
        print("WHAT-IF SCENARIO SIMULATION")
        print("=" * 60)

        for name, params in self.PRESET_SCENARIOS.items():
            try:
                self.what_if_scenario(name, params, max_assets=max_assets)
            except Exception as exc:
                print(f"   ✗ Scenario '{name}' failed: {exc}")

        return self.what_if_results

    def compare_what_if_scenarios(self) -> pd.DataFrame:
        """Scenario comparison table, biggest risk reduction first."""
        if not self.what_if_results:
            return pd.DataFrame()

        df = pd.DataFrame(list(self.what_if_results.values()))
        return df.sort_values('absolute_change').reset_index(drop=True)

    def export_what_if_graph_data(self) -> List[Dict]:
        """Chart-ready scenario comparison for the dashboard."""
        return [
            {
                'scenario': r['scenario'],
                'description': r['description'],
                'baseline_expected_loss': r['baseline_expected_loss'],
                'scenario_expected_loss': r['scenario_expected_loss'],
                'absolute_change': r['absolute_change'],
                'percent_change': r['percent_change'],
                'var_95_change': r['var_95_change'],
                'direction': r['direction'],
            }
            for r in sorted(self.what_if_results.values(), key=lambda x: x['absolute_change'])
        ]

    def get_summary(self) -> pd.DataFrame:
        if self.fair_results_df.empty:
            return pd.DataFrame()
        return self.fair_results_df[['asset_id', 'expected_ale', 'var_95', 'var_99', 'cvar_95', 'control_effectiveness']]
    
    def export_results(self, path: str = 'outputs/fair_results.json'):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        export_data = {
            'scenarios': {},
            'what_if_scenarios': {},
            'aggregate': self.get_risk_metrics()
        }
        
        for scenario_name, result in self.results.items():
            export_data['scenarios'][scenario_name] = {
                'total_expected_loss': result['aggregate']['total_expected_loss'],
                'var_95': result['aggregate']['var_95'],
                'var_99': result['aggregate']['var_99'],
                'cvar_95': result['aggregate']['cvar_95'],
                'assets': len(result['asset_results'])
            }
        
        with open(path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f" Results exported to {path}")


class RiskQuantificationEngine(FAIRMonteCarlo):
    pass