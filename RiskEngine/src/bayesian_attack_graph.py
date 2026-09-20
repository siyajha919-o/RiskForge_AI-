"""
Bayesian Attack Graph 
"""

import pandas as pd
import numpy as np
import networkx as nx
from typing import Dict, List, Optional, Tuple
import warnings
import json
import os
import time
warnings.filterwarnings('ignore')


class BayesianAttackGraph: 
    def __init__(self, data: Optional[Dict[str, pd.DataFrame]] = None, 
                 config: Optional[Dict] = None):
        self.data = data or {}
        self.config = config or {}
        self.graph = nx.DiGraph()
        self.attack_paths = []
        self.attack_probabilities = {}
        self.critical_paths = {}
        self.performance_stats = {}
        
        
        self.max_paths = self.config.get('max_paths', 20)
        self.path_cutoff = self.config.get('path_cutoff', 3)
        self.min_probability = self.config.get('min_probability', 0.05)
        self.max_assets = self.config.get('max_assets', 100)
        
        print("\n" + "="*60)
        print("BAYESIAN ATTACK GRAPH ")
        print("="*60)
        print(f"Max Paths: {self.max_paths}")
        print(f"Max Assets: {self.max_assets}")
        print(f"Min Probability: {self.min_probability}")
    
    def _extract_vulnerability_data(self) -> pd.DataFrame: 
        asset_profile = self.data.get('asset_risk_profile', pd.DataFrame())
        risk_matrix = self.data.get('risk_matrix', pd.DataFrame())
         
        if not asset_profile.empty:
            vuln_cols = ['vuln_count', 'avg_cvss', 'max_cvss', 'avg_epss', 
                        'avg_days_open', 'critical_vuln_count']
            has_vuln_data = any(col in asset_profile.columns for col in vuln_cols)
            
            if has_vuln_data:
                vuln_df = asset_profile[['asset_id']].copy()
                 
                col_mapping = {
                    'vuln_count': 'total_vulns',
                    'avg_cvss': 'cvss_score',
                    'max_cvss': 'max_cvss',
                    'avg_epss': 'epss_score',
                    'avg_days_open': 'days_open',
                    'critical_vuln_count': 'critical_vulns'
                }
                
                for old_col, new_col in col_mapping.items():
                    if old_col in asset_profile.columns:
                        vuln_df[new_col] = asset_profile[old_col]
                 
                if 'cvss_score' in vuln_df.columns:
                    vuln_df['severity'] = pd.cut(
                        vuln_df['cvss_score'],
                        bins=[-0.1, 3.9, 6.9, 8.9, 10.1],
                        labels=['Low', 'Medium', 'High', 'Critical']
                    )
                 
                vuln_df['cve_id'] = vuln_df['asset_id'].apply(lambda x: f'CVE-{x[:8]}')
                vuln_df['vulnerability_id'] = vuln_df['asset_id'].apply(lambda x: f'VULN-{x[:8]}')
                vuln_df['asset_id'] = vuln_df['asset_id']
                
                return vuln_df
         
        if not risk_matrix.empty:
            vuln_cols = ['vuln_count', 'avg_cvss', 'max_cvss']
            has_vuln_data = any(col in risk_matrix.columns for col in vuln_cols)
            
            if has_vuln_data:
                vuln_df = risk_matrix[['asset_id']].copy()
                
                col_mapping = {
                    'vuln_count': 'total_vulns',
                    'avg_cvss': 'cvss_score',
                    'max_cvss': 'max_cvss'
                }
                
                for old_col, new_col in col_mapping.items():
                    if old_col in risk_matrix.columns:
                        vuln_df[new_col] = risk_matrix[old_col]
                
                if 'cvss_score' in vuln_df.columns:
                    vuln_df['severity'] = pd.cut(
                        vuln_df['cvss_score'],
                        bins=[-0.1, 3.9, 6.9, 8.9, 10.1],
                        labels=['Low', 'Medium', 'High', 'Critical']
                    )
                
                vuln_df['cve_id'] = vuln_df['asset_id'].apply(lambda x: f'CVE-{x[:8]}')
                vuln_df['vulnerability_id'] = vuln_df['asset_id'].apply(lambda x: f'VULN-{x[:8]}')
                
                return vuln_df
         
        vuln = self.data.get('vulnerabilities', pd.DataFrame())
        if not vuln.empty:
            return vuln
        
        return pd.DataFrame()
    
    def _get_criticality_value(self, asset) -> float: 
        if isinstance(asset, dict):
            for col in ['asset_criticality', 'criticality', 'current_risk_score']:
                if col in asset and asset[col] is not None:
                    val = asset[col]
                    if isinstance(val, (int, float)):
                        return float(val)
                    if isinstance(val, str):
                        if val.lower() in ['critical', 'high']:
                            return 8
                        elif val.lower() == 'medium':
                            return 5
                        elif val.lower() in ['low', 'very low']:
                            return 3
        return 5
    
    def _get_exploit_probability(self, vuln) -> float: 
        if isinstance(vuln, dict): 
            if 'epss_score' in vuln and vuln['epss_score'] is not None:
                try:
                    return min(float(vuln['epss_score']), 0.99)
                except:
                    pass
             
            if 'cvss_score' in vuln and vuln['cvss_score'] is not None:
                try:
                    cvss = float(vuln['cvss_score'])
                    return min(0.1 + (cvss / 10) * 0.6, 0.99)
                except:
                    pass 
        if hasattr(vuln, 'get'):
            if 'epss_score' in vuln and vuln['epss_score'] is not None:
                try:
                    return min(float(vuln['epss_score']), 0.99)
                except:
                    pass
            
            if 'cvss_score' in vuln and vuln['cvss_score'] is not None:
                try:
                    cvss = float(vuln['cvss_score'])
                    return min(0.1 + (cvss / 10) * 0.6, 0.99)
                except:
                    pass
        
        return 0.3
    
    def build_graph(self, assets: Optional[pd.DataFrame] = None, 
                    vulns: Optional[pd.DataFrame] = None) -> Dict: 
        start_time = time.time()
        
        print("\n🔨 Building attack graph...")
         
        if assets is None:
            assets = self.data.get('assets')
         
        if assets is None or assets.empty:
            assets = self.data.get('asset_risk_profile')
         
        if vulns is None or vulns.empty:
            vulns = self._extract_vulnerability_data()
        
        if assets is None or assets.empty:
            print("✗ No assets data")
            return {'error': 'No assets data'}
        
        if vulns is None or vulns.empty:
            print("✗ No vulnerabilities data found in merged data")
            return {'error': 'No vulnerabilities data'}
         
        original_assets = len(assets)
        if len(assets) > self.max_assets:
            assets = assets.head(self.max_assets)
            print(f"  Limited to {self.max_assets} assets (from {original_assets})")
         
        asset_count = 0
        vuln_count = 0
        edge_count = 0
         
        for _, asset in assets.iterrows():
            asset_id = asset.get('asset_id', f'asset_{asset_count}')
            criticality = self._get_criticality_value(asset.to_dict())
            
            self.graph.add_node(
                asset_id,
                type='asset',
                name=asset.get('asset_name', f'Asset_{asset_id}'),
                criticality=criticality
            )
            asset_count += 1
        
        
        for _, v in vulns.iterrows():
            vuln_dict = v.to_dict()
            exploit_prob = self._get_exploit_probability(vuln_dict)
             
            cvss = 5.0
            if 'cvss_score' in v and not pd.isna(v['cvss_score']):
                try:
                    cvss = float(v['cvss_score'])
                except:
                    pass
            
            vuln_id = v.get('vulnerability_id', v.get('cve_id', f'vuln_{vuln_count}'))
            
            self.graph.add_node(
                vuln_id,
                type='vulnerability',
                cve=v.get('cve_id', f'CVE-{vuln_id}'),
                cvss=cvss,
                exploit_prob=exploit_prob
            )
            vuln_count += 1
             
            if 'asset_id' in v and v['asset_id'] in self.graph:
                self.graph.add_edge(
                    vuln_id,
                    v['asset_id'],
                    weight=cvss / 10.0,
                    exploit_prob=exploit_prob
                )
                edge_count += 1
        
        elapsed = time.time() - start_time
        
        self.performance_stats['build_time'] = elapsed
        
        print(f"  ✓ Added {asset_count} assets, {vuln_count} vulnerabilities, {edge_count} edges")
        print(f"  ✓ Build time: {elapsed:.2f}s")
        print(f"Graph ready: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
        return {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'assets': asset_count,
            'vulnerabilities': vuln_count
        }
    
    def find_attack_paths(self, max_paths: int = None) -> List[Dict]: 
        start_time = time.time()
        
        print("\nFinding attack paths...")
        
        if self.graph.number_of_nodes() == 0:
            print("✗ Graph is empty")
            return []
        
        max_paths = max_paths or self.max_paths
         
        vulnerabilities = [n for n, d in self.graph.nodes(data=True) 
                          if d.get('type') == 'vulnerability']
         
        assets = []
        for n, d in self.graph.nodes(data=True):
            if d.get('type') == 'asset':
                try:
                    criticality = float(d.get('criticality', 5))
                    if criticality >= 5:
                        assets.append(n)
                except:
                    assets.append(n)
        
        if not vulnerabilities or not assets:
            print("⚠ Not enough data for paths")
            return []
         
        vuln_limit = min(len(vulnerabilities), 15)
        asset_limit = min(len(assets), 8)
        
        print(f"  Analyzing {vuln_limit} vulnerabilities → {asset_limit} critical assets")
        
        attack_paths = []
        paths_found = 0
        
        for vuln_id in vulnerabilities[:vuln_limit]:
            for asset_id in assets[:asset_limit]:
                try:
                    if nx.has_path(self.graph, vuln_id, asset_id):
                        path = nx.shortest_path(self.graph, vuln_id, asset_id)
                        path_len = len(path) - 1
                        
                        if path_len <= self.path_cutoff:
                            path_prob = self._calculate_path_probability(path)
                            if path_prob >= self.min_probability:
                                attack_paths.append({
                                    'path': path,
                                    'probability': path_prob,
                                    'target': asset_id,
                                    'length': path_len
                                })
                                paths_found += 1
                except:
                    continue
         
        attack_paths.sort(key=lambda x: x['probability'], reverse=True)
        self.attack_paths = attack_paths[:max_paths]
        
        elapsed = time.time() - start_time
        self.performance_stats['path_time'] = elapsed
        
        print(f"  ✓ Found {paths_found} paths, kept {len(self.attack_paths)}")
        print(f"  ✓ Path finding time: {elapsed:.2f}s")
        
        if self.attack_paths:
            print("\nTop Attack Paths:")
            for i, p in enumerate(self.attack_paths[:5]):
                path_str = ' → '.join(p['path'][:4])
                if len(p['path']) > 4:
                    path_str += ' → ...'
                print(f"    {i+1}. {path_str}")
                print(f"       Probability: {p['probability']:.3f}, Length: {p['length']}")
        else:
            print("⚠ No attack paths found above threshold")
        
        return self.attack_paths
    
    def _calculate_path_probability(self, path: List[str]) -> float: 
        prob = 1.0
        
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i+1])
            if edge_data and 'exploit_prob' in edge_data:
                prob *= float(edge_data['exploit_prob'])
            else:
                prob *= 0.3
         
        prob *= (1.0 / (1 + 0.15 * (len(path) - 1)))
        
        return min(max(prob, 0.001), 1.0)
    
    def calculate_attack_probabilities(self) -> pd.DataFrame: 
        print("\nCalculating attack probabilities...")
        
        if not self.attack_paths:
            self.find_attack_paths()
            if not self.attack_paths:
                return pd.DataFrame()
         
        attack_probs = {}
        for path_data in self.attack_paths:
            target = path_data.get('target')
            prob = path_data.get('probability', 0)
            if target:
                if target not in attack_probs:
                    attack_probs[target] = []
                attack_probs[target].append(prob)
        
        results = []
        for asset_id, probs in attack_probs.items(): 
            union_prob = 1 - np.prod([1 - min(p, 1.0) for p in probs])
             
            criticality = 5
            if asset_id in self.graph:
                try:
                    criticality = float(self.graph.nodes[asset_id].get('criticality', 5))
                except:
                    criticality = 5
            
            results.append({
                'asset_id': asset_id,
                'attack_path_count': len(probs),
                'attack_probability': min(union_prob, 1.0),
                'criticality': criticality,
                'risk_score': min(union_prob * (criticality / 5), 1.0)
            })
        
        if not results:
            return pd.DataFrame()
        
        results_df = pd.DataFrame(results).sort_values('risk_score', ascending=False)
        
        print(f"Calculated for {len(results_df)} assets")
        
        if not results_df.empty:
            top = results_df.iloc[0]
            print(f"\nHighest Risk Asset:")
            print(f"  Asset: {top['asset_id']}")
            print(f"  Attack Probability: {top['attack_probability']:.3f}")
            print(f"  Risk Score: {top['risk_score']:.3f}")
            print(f"  Criticality: {top['criticality']:.0f}")
            print(f"  Attack Paths: {top['attack_path_count']}")
        
        return results_df
    
    def identify_critical_paths(self, top_n: int = 5) -> Dict: 
        print("\nIdentifying critical paths...")
        
        if not self.attack_paths:
            if self.graph.number_of_nodes() > 0:
                self.find_attack_paths()
            if not self.attack_paths:
                return {'critical_paths': [], 'high_risk_assets': []}
         
        critical_paths = [p for p in self.attack_paths if p.get('probability', 0) > 0.15]
        critical_paths = critical_paths[:top_n]
         
        high_risk_assets = []
        if self.attack_paths:
            asset_risk = {}
            for p in self.attack_paths:
                target = p.get('target')
                prob = p.get('probability', 0)
                if target:
                    if target not in asset_risk:
                        asset_risk[target] = []
                    asset_risk[target].append(prob)
            
            sorted_assets = sorted(
                asset_risk.items(),
                key=lambda x: max(x[1]) if x[1] else 0,
                reverse=True
            )
            high_risk_assets = [asset for asset, _ in sorted_assets[:top_n]]
        
        self.critical_paths = {
            'critical_paths': critical_paths,
            'high_risk_assets': high_risk_assets
        }
        
        print(f"Found {len(critical_paths)} critical paths")
        
        if critical_paths:
            print("\nCritical Attack Paths:")
            for i, path in enumerate(critical_paths):
                path_str = ' → '.join(path.get('path', [])[:4])
                if len(path.get('path', [])) > 4:
                    path_str += ' → ...'
                print(f"  {i+1}. {path_str}")
                print(f"     Probability: {path.get('probability', 0):.3f}")
        
        return self.critical_paths
    
    def find_critical_attack_paths(self, n_paths: int = 5) -> List[Dict]: 
        if not self.attack_paths:
            self.find_attack_paths()
        
        if not self.attack_paths:
            return []
        
        top_paths = self.attack_paths[:n_paths]
        
        formatted_paths = []
        for path in top_paths:
            path_nodes = path.get('path', [])
            path_prob = path.get('probability', 0)
            
            target = path.get('target')
            expected_loss = path_prob * 5000000
            
            if target and target in self.graph:
                try:
                    criticality = float(self.graph.nodes[target].get('criticality', 5))
                    expected_loss *= (criticality / 5)
                except:
                    pass
            
            formatted_paths.append({
                'path': path_nodes,
                'probability': path_prob,
                'expected_loss': expected_loss,
                'target': target
            })
        
        return formatted_paths
    
    def get_summary(self) -> Dict: 
        return {
            'graph_stats': {
                'nodes': self.graph.number_of_nodes(),
                'edges': self.graph.number_of_edges(),
                'vulnerabilities': len([n for n, d in self.graph.nodes(data=True) 
                                       if d.get('type') == 'vulnerability']),
                'assets': len([n for n, d in self.graph.nodes(data=True) 
                              if d.get('type') == 'asset'])
            },
            'attack_paths': {
                'total_found': len(self.attack_paths),
                'top_paths': self.attack_paths[:5]
            },
            'performance': self.performance_stats
        }
    
    def export_results(self, path: str = 'outputs/attack_graph_results.json'): 
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        export_data = {
            'graph_stats': {
                'nodes': self.graph.number_of_nodes(),
                'edges': self.graph.number_of_edges(),
                'vulnerabilities': len([n for n, d in self.graph.nodes(data=True) 
                                       if d.get('type') == 'vulnerability']),
                'assets': len([n for n, d in self.graph.nodes(data=True) 
                              if d.get('type') == 'asset'])
            },
            'attack_paths': [
                {
                    'path': p.get('path', []),
                    'probability': p.get('probability', 0),
                    'target': p.get('target', ''),
                    'length': p.get('length', 0)
                }
                for p in self.attack_paths[:10]
            ],
            'critical_paths': self.critical_paths,
            'performance': self.performance_stats
        }
        
        with open(path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        print(f"Results exported to {path}")

 