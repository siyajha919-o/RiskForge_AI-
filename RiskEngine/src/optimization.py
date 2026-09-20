  

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Optional, List, Tuple
import warnings
import os
import json
warnings.filterwarnings('ignore')


class InvestmentOptimizer:
    """Investment Optimization with Realistic Risk Reduction"""
    
    def __init__(self, data: Dict[str, pd.DataFrame], config: Optional[Dict] = None):
        self.data = data
        self.config = config or {}
        self.gordon_loeb_factor = self.config.get('gordon_loeb_factor', 0.37)
        # No control portfolio eliminates risk, so reduction asymptotes toward a
        # ceiling. It is a SCALE, never a clamp — see _calculate_combined_reduction.
        self.max_reduction_pct = self.config.get('max_risk_reduction_pct', 85.0)
        # Controls overlap: the Nth control added to a maturing programme
        # mitigates risk the first N-1 already partly cover. Without this,
        # treating controls as independent saturates the ceiling at ~10 of them.
        self.overlap_decay = self.config.get('control_overlap_decay', 0.9)
        self.results = {}
        
        print("\n" + "="*60)
        print(" INVESTMENT OPTIMIZATION ENGINE")
        print("="*60)
        print(f"Gordon-Loeb Factor: {self.gordon_loeb_factor * 100}%")
        print(f"Max investment per control: {self.gordon_loeb_factor * 100}% of expected loss")
    
    def _calculate_combined_reduction(self, selected_items: pd.DataFrame) -> float:
        """
        Calculate combined risk reduction using multiplicative formula:
        1 - product of (1 - individual_reduction)
        This is realistic - controls don't simply add up
        """
        if selected_items.empty:
            return 0.0
        
        # Get individual reduction percentages (0-1 scale)
        if 'risk_reduction_percentage' in selected_items.columns:
            eff = selected_items['risk_reduction_percentage'] / 100.0
        elif 'effectiveness_score' in selected_items.columns:
            eff = selected_items['effectiveness_score']
        else:
            return 0.0
        
        # Cap at 0.40 (40%) per control - realistic maximum
        eff = np.asarray(eff, dtype=float)
        eff = np.clip(eff, 0, 0.40)
        if eff.size == 0:
            return 0.0

        # Strongest control first, then discount each subsequent one by
        # overlap_decay**rank. Two controls that both harden the same attack path
        # do not each remove an independent 40% of the risk, and assuming they do
        # is what made the efficient frontier flat: under pure independence six
        # controls reach 81% and twenty are indistinguishable from the 85%
        # ceiling, so every larger budget returned the same number.
        eff = np.sort(eff)[::-1]
        eff = eff * (self.overlap_decay ** np.arange(eff.size))

        # Combined formula: 1 - product(1 - eff). Each additional control buys
        # strictly less than the one before it, and the total approaches the
        # ceiling without ever being clamped to it.
        combined = 1 - np.prod(1 - eff)

        return float(self.max_reduction_pct * combined)
    
    def _validate_controls(self, controls: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean controls data - FIXED: Cap at 40%"""
        result = controls.copy()
        
        if 'risk_reduction_percentage' in result.columns:
            # FIX: Cap at 40% (realistic) not 100%
            result['risk_reduction_percentage'] = result['risk_reduction_percentage'].clip(5, 40)
        
        if 'annual_cost' in result.columns:
            result['annual_cost'] = result['annual_cost'].clip(0)
        
        # Remove invalid rows
        result = result[(result['annual_cost'] > 0) & (result['risk_reduction_percentage'] > 0)]
        
        return result
    
    def solve_knapsack(self, items: pd.DataFrame, budget: float) -> Dict:
        """
        Solve 0-1 knapsack problem for optimal control selection
        """
        print("\n" + "-"*40)
        print(" KNAPSACK OPTIMIZATION")
        print("-"*40)
        print(f"Budget: ₹{budget:,.2f}")
        print(f"Items: {len(items)}")
        
        if len(items) == 0:
            return {
                'selected_items': [],
                'total_value': 0,
                'total_cost': 0,
                'selected_details': pd.DataFrame()
            }
        
        items = self._validate_controls(items)
        
        if len(items) == 0:
            print("⚠ No valid items after validation")
            return {
                'selected_items': [],
                'total_value': 0,
                'total_cost': 0,
                'selected_details': pd.DataFrame()
            }
        
        items_sorted = items.copy()
        items_sorted['value_ratio'] = items_sorted['risk_reduction_percentage'] / (items_sorted['annual_cost'] + 1)
        items_sorted = items_sorted.sort_values('value_ratio', ascending=False)
        
        selected_indices = []
        total_cost = 0
        selected_details = []
        
        expected_loss = self._get_expected_loss()
        max_investment_per_control = expected_loss * self.gordon_loeb_factor
        
        for idx, item in items_sorted.iterrows():
            cost = item['annual_cost']
            
            if cost > max_investment_per_control:
                continue
            
            if total_cost + cost <= budget:
                selected_indices.append(idx)
                total_cost += cost
                selected_details.append({
                    'control_id': idx,
                    'control_name': item.get('control_name', f'Control_{idx}'),
                    'annual_cost': cost,
                    'risk_reduction': item['risk_reduction_percentage'],
                    'value_ratio': item['value_ratio'],
                    'cumulative_cost': total_cost
                })
        
        # ============================================================
        # FIX: Calculate combined reduction using multiplicative formula
        # ============================================================
        if selected_indices:
            selected_items_df = items_sorted.loc[selected_indices]
            total_value = self._calculate_combined_reduction(selected_items_df)
        else:
            total_value = 0
        
        print(f"\n Knapsack Results:")
        print(f"  Selected: {len(selected_indices)} items")
        print(f"  Combined Risk Reduction: {total_value:.2f}%")
        print(f"  Total Cost: ₹{total_cost:,.2f}")
        print(f"  Budget Utilization: {(total_cost/budget*100):.1f}%")
        
        return {
            'selected_items': selected_indices,
            'total_value': total_value,
            'total_cost': total_cost,
            'selected_details': pd.DataFrame(selected_details) if selected_details else pd.DataFrame()
        }
    
    def _get_expected_loss(self) -> float:
        """Get expected annual loss from risk calculations or ML predictions"""
        risk_data = self.data.get('risk_calculations', pd.DataFrame())
        if not risk_data.empty and 'expected_annual_loss' in risk_data.columns:
            return risk_data['expected_annual_loss'].sum()
        
        risk_matrix = self.data.get('risk_matrix', pd.DataFrame())
        if not risk_matrix.empty and 'expected_loss' in risk_matrix.columns:
            return risk_matrix['expected_loss'].sum()
        
        asset_profile = self.data.get('asset_risk_profile', pd.DataFrame())
        if not asset_profile.empty and 'expected_loss' in asset_profile.columns:
            return asset_profile['expected_loss'].sum()
        
        return 10000000
    
    def calculate_rosi(self, risk_reduction: float, cost: float) -> float:
        """
        Calculate Return on Security Investment (ROSI)
        ROSI = (Risk Reduction - Cost) / Cost
        """
        if cost <= 0:
            return 0
        
        # Already scaled by _calculate_combined_reduction; guard only against
        # upstream columns that exceed the ceiling.
        risk_reduction = min(risk_reduction, self.max_reduction_pct)
        
        expected_loss = self._get_expected_loss()
        financial_reduction = expected_loss * (risk_reduction / 100)
        
        rosi = (financial_reduction - cost) / cost
        
        # Cap at reasonable maximum
        rosi = min(rosi, 100)
        
        return rosi
    
    def calculate_roi(self, risk_reduction: float, cost: float) -> float:
        """Calculate Return on Investment (ROI) as percentage"""
        if cost <= 0:
            return 0
        
        risk_reduction = min(risk_reduction, self.max_reduction_pct)
        expected_loss = self._get_expected_loss()
        financial_reduction = expected_loss * (risk_reduction / 100)
        
        roi = (financial_reduction / cost) * 100
        
        roi = min(roi, 10000)
        
        return roi
    
    def gordon_loeb_constraint(self, expected_loss: float) -> Dict:
        """Apply Gordon-Loeb constraint (≤37% of expected loss)"""
        max_investment = expected_loss * self.gordon_loeb_factor
        
        return {
            'max_investment': max_investment,
            'factor': self.gordon_loeb_factor,
            'expected_loss': expected_loss,
            'is_valid': True
        }
    
    def _prepare_controls(self, controls: pd.DataFrame) -> pd.DataFrame:
        """Prepare controls DataFrame with required columns - FIXED"""
        result = controls.copy()
        
        if 'annual_cost' not in result.columns:
            if 'implementation_cost' in result.columns:
                result['annual_cost'] = result['implementation_cost']
            elif 'cost' in result.columns:
                result['annual_cost'] = result['cost']
            else:
                result['annual_cost'] = 0
        
        if 'risk_reduction_percentage' not in result.columns:
            if 'expected_risk_reduction' in result.columns:
                result['risk_reduction_percentage'] = result['expected_risk_reduction']
            elif 'effectiveness_score' in result.columns:
                # FIX: Cap at 40% for realistic single control
                result['risk_reduction_percentage'] = result['effectiveness_score'] * 40
            else:
                result['risk_reduction_percentage'] = np.random.uniform(5, 30, len(result))
        
        # FIX: Cap at 40% (realistic)
        result['risk_reduction_percentage'] = result['risk_reduction_percentage'].clip(5, 40)
        
        if 'control_id' not in result.columns:
            result['control_id'] = result.index
        
        if 'control_name' not in result.columns:
            if 'name' in result.columns:
                result['control_name'] = result['name']
            else:
                result['control_name'] = result['control_id'].astype(str)
        
        return result
    
    def optimize_investment_portfolio(self,
                                     controls: pd.DataFrame,
                                     budget: float,
                                     expected_loss: Optional[float] = None) -> Dict:
        """
        Complete investment optimization pipeline
        """
        print("\n" + "="*60)
        print(" INVESTMENT PORTFOLIO OPTIMIZATION")
        print("="*60)
        
        controls_clean = self._prepare_controls(controls)
        controls_clean = self._validate_controls(controls_clean)
        
        if controls_clean.empty:
            print("⚠ No valid controls after validation")
            return {'error': 'No valid controls'}
        
        if expected_loss is None:
            expected_loss = self._get_expected_loss()
        
        print(f"Expected Annual Loss: ₹{expected_loss:,.2f}")
        print(f"Budget: ₹{budget:,.2f}")
        
        gl_result = self.gordon_loeb_constraint(expected_loss)
        print(f"Gordon-Loeb Max Investment per Control: ₹{gl_result['max_investment']:,.2f}")
        
        knapsack_result = self.solve_knapsack(controls_clean, budget)
        
        # FIX: Total risk reduction already combined from knapsack
        total_risk_reduction = min(knapsack_result['total_value'], self.max_reduction_pct)
        
        rosi = self.calculate_rosi(total_risk_reduction, knapsack_result['total_cost'])
        roi = self.calculate_roi(total_risk_reduction, knapsack_result['total_cost'])
        
        financial_reduction = expected_loss * (total_risk_reduction / 100)
        residual_risk = expected_loss - financial_reduction
        
        result = {
            'total_investment': knapsack_result['total_cost'],
            'total_risk_reduction': total_risk_reduction,
            'financial_reduction': financial_reduction,
            'residual_risk': residual_risk,
            'rosi': rosi,
            'roi': roi,
            'gordon_loeb': gl_result,
            'selected_items': knapsack_result['selected_items'],
            'selected_details': knapsack_result['selected_details'],
            'budget': budget,
            'expected_loss': expected_loss,
            'budget_utilization': (knapsack_result['total_cost'] / budget * 100) if budget > 0 else 0
        }
        
        print(f"\n{'='*50}")
        print(" INVESTMENT PORTFOLIO RESULTS")
        print('='*50)
        print(f"  Total Investment: ₹{knapsack_result['total_cost']:,.2f}")
        print(f"  Budget Utilization: {result['budget_utilization']:.1f}%")
        print(f"  Risk Reduction: {total_risk_reduction:.2f}%")
        print(f"  Financial Reduction: ₹{financial_reduction:,.2f}")
        print(f"  Residual Risk: ₹{residual_risk:,.2f}")
        print(f"  ROSI: {rosi:.2f}x")
        print(f"  ROI: {roi:.2f}%")
        print(f"  Gordon-Loeb Max: ₹{gl_result['max_investment']:,.2f}")
        
        if rosi > 0:
            print(f"  ✅ ROSI > 0: Investment is profitable")
        else:
            print(f"  ⚠ ROSI ≤ 0: Investment may not be profitable")
        
        self.results = result
        return result
    
    def plot_efficient_frontier(self,
                               controls: Optional[pd.DataFrame] = None,
                               max_budget: Optional[float] = None,
                               n_points: int = 20) -> None:
        """Plot efficient frontier curve showing risk reduction vs investment"""
        print("\n" + "="*60)
        print(" GENERATING EFFICIENT FRONTIER")
        print("="*60)
        
        if controls is None:
            controls = self.data.get('security_controls', pd.DataFrame())
        
        if controls.empty:
            print("⚠ No controls data available for frontier")
            return
        
        controls_clean = self._prepare_controls(controls)
        controls_clean = self._validate_controls(controls_clean)
        
        if controls_clean.empty:
            print("⚠ No valid controls after validation")
            return
        
        if max_budget is None:
            max_budget = min(controls_clean['annual_cost'].sum(), 100000000)
        
        print(f"Max Budget: ₹{max_budget:,.2f}")
        print(f"Number of points: {n_points}")
        frontier_points = []
        
        for budget_fraction in np.linspace(0.05, 0.95, n_points):
            budget = max_budget * budget_fraction
            result = self.solve_knapsack(controls_clean, budget)
            
            if result['total_cost'] > 0:
                total_value = min(result['total_value'], self.max_reduction_pct)
                rosi = self.calculate_rosi(total_value, result['total_cost'])
                roi = self.calculate_roi(total_value, result['total_cost'])
                frontier_points.append({
                    'budget': result['total_cost'],
                    'risk_reduction': total_value,
                    'rosi': rosi,
                    'roi': roi,
                    'budget_fraction': budget_fraction
                })
        
        if not frontier_points:
            print("⚠ No frontier points generated")
            return
        
        points_df = pd.DataFrame(frontier_points)
        
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        # Risk Reduction
        ax1 = axes[0]
        ax1.plot(points_df['budget'], points_df['risk_reduction'], 'b-', linewidth=2)
        ax1.scatter(points_df['budget'], points_df['risk_reduction'], c='blue', s=50, alpha=0.6)
        ax1.set_xlabel('Investment Budget (₹)')
        ax1.set_ylabel('Risk Reduction (%)')
        ax1.set_title('Efficient Frontier: Risk Reduction')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1e6:.1f}M'))
        ax1.set_ylim(0, 100)
        
        # ROSI
        ax2 = axes[1]
        ax2.plot(points_df['budget'], points_df['rosi'], 'r-', linewidth=2)
        ax2.scatter(points_df['budget'], points_df['rosi'], c='red', s=50, alpha=0.6)
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax2.set_xlabel('Investment Budget (₹)')
        ax2.set_ylabel('ROSI')
        ax2.set_title('Efficient Frontier: ROSI')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1e6:.1f}M'))
        ax2.set_ylim(0, 10)
        
        # ROI
        ax3 = axes[2]
        ax3.plot(points_df['budget'], points_df['roi'], 'g-', linewidth=2)
        ax3.scatter(points_df['budget'], points_df['roi'], c='green', s=50, alpha=0.6)
        ax3.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Investment Budget (₹)')
        ax3.set_ylabel('ROI (%)')
        ax3.set_title('Efficient Frontier: ROI')
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₹{x/1e6:.1f}M'))
        ax3.set_ylim(0, 500)
        
        plt.tight_layout()
        
        os.makedirs('outputs', exist_ok=True)
        plt.savefig('outputs/efficient_frontier.png', dpi=150, bbox_inches='tight')
        print(" Efficient frontier saved to 'outputs/efficient_frontier.png'")
        
        points_df.to_csv('outputs/efficient_frontier_data.csv', index=False)
        print(" Frontier data saved to 'outputs/efficient_frontier_data.csv'")
        
        plt.close()
        
        print(f"\n📊 Frontier Summary:")
        print(f"  Max Risk Reduction: {points_df['risk_reduction'].max():.2f}%")
        print(f"  Max ROSI: {points_df['rosi'].max():.2f}x")
        print(f"  Max ROI: {points_df['roi'].max():.2f}%")
    
    def get_optimization_summary(self) -> Dict:
        """Get summary of optimization results"""
        return self.results
    
    def export_results(self, path: str = 'outputs/optimization_results.json'): 
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        results_copy = self.results.copy()
        if 'selected_items' in results_copy:
            results_copy['selected_items'] = [int(x) for x in results_copy['selected_items']]
        
        if 'selected_details' in results_copy and not results_copy['selected_details'].empty:
            results_copy['selected_details'] = results_copy['selected_details'].to_dict('records')
        
        with open(path, 'w') as f:
            json.dump(results_copy, f, indent=2, default=str)
        
        print(f" Results exported to {path}")
    
    def get_tensorflow_ready_data(self) -> Tuple[np.ndarray, np.ndarray]: 
        controls = self.data.get('security_controls', pd.DataFrame())
        
        if controls.empty:
            return np.array([]), np.array([])
        
        controls_clean = self._prepare_controls(controls)
        controls_clean = self._validate_controls(controls_clean)
        
        feature_cols = ['annual_cost']
        if 'effectiveness_score' in controls_clean.columns:
            feature_cols.append('effectiveness_score')
        if 'coverage_percentage' in controls_clean.columns:
            feature_cols.append('coverage_percentage')
        
        features = controls_clean[feature_cols].fillna(0).values
        targets = controls_clean['risk_reduction_percentage'].values
        
        return features, targets