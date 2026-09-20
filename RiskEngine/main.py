"""
Cyber Risk Quantification & Investment Optimization Platform 
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import sys
import json
import argparse
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

from src.data_loader import CyberRiskDataLoader
from src.preprocess import DataPreprocessor
from src.data_merger import DataMerger
from src.feature_engineering import FeatureEngineer
from src.model import CyberRiskModels
from src.fair_monte_carlo import FAIRMonteCarlo
from src.optimization import InvestmentOptimizer
from src.business_unit_rollup import BusinessUnitRollup
from src.compliance import ComplianceMapper, ComplianceReportGenerator, ComplianceDataError
from src.bayesian_attack_graph import BayesianAttackGraph
from src.audit import AuditLog
from src.remediation import RemediationPlanner
from src.risk_history import RiskHistory
from src.conf import config

parser = argparse.ArgumentParser(description="Cyber risk quantification pipeline")
parser.add_argument(
    '--mode',
    choices=['full', 'incremental'],
    default='full',
    help="'full' retrains the ML models; 'incremental' reuses saved models for a fast refresh."
)
parser.add_argument(
    '--skip-attack-graph',
    action='store_true',
    help="Skip Bayesian attack path analysis (the slowest optional stage)."
)
parser.add_argument(
    '--skip-scenarios',
    action='store_true',
    help="Skip what-if scenario simulation."
)
args = parser.parse_args()
RUN_MODE = args.mode

os.makedirs('outputs', exist_ok=True)
os.makedirs('models', exist_ok=True)

print("="*80)
print(f"RISK ENGINE - {RUN_MODE.upper()} RUN")
print("="*80)
print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

start_total = datetime.now()

# ============================================================================
# DATA LOADING
# ============================================================================
start = datetime.now()
loader = CyberRiskDataLoader(data_path=str(config.get_data_path()))
raw_data = loader.load_all_data(impute=True)
if not raw_data:
    print("No data loaded!")
    sys.exit(1)
print(f"Data loaded in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# PREPROCESSING
# ============================================================================
start = datetime.now()
preprocessor = DataPreprocessor(raw_data)
processed_data = preprocessor.preprocess_all()
print(f"Preprocessed in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# LIVE ENDPOINT DEVICES
# ============================================================================
# Agents reporting real machines append to data/live_devices.csv. Merging them
# into the asset estate here means a laptop's open port or disabled firewall
# flows through FAIR, the business-unit rollup and the optimizer exactly like
# any other asset — rather than sitting in a separate "IoT" panel.
_live_path = config.get_data_path('live_devices.csv')
live_device_count = 0

if os.path.exists(_live_path):
    try:
        _live = pd.read_csv(_live_path)
        if not _live.empty:
            _assets = processed_data.get('assets', pd.DataFrame())
            _shared = [c for c in _live.columns if c in _assets.columns] if not _assets.empty else list(_live.columns)
            if not _assets.empty:
                _assets = _assets[~_assets['asset_id'].isin(_live['asset_id'])]
                # Live devices go first: FAIR simulates a capped number of assets,
                # and a machine that is actively reporting must never be the one
                # cut from the sample.
                processed_data['assets'] = pd.concat([_live[_shared], _assets], ignore_index=True)
            else:
                processed_data['assets'] = _live
            live_device_count = len(_live)
            print(f"Merged {live_device_count} live endpoint device(s) into the asset estate")
    except Exception as exc:
        print(f"Could not merge live devices: {exc}")

# ============================================================================
# DATA MERGING
# ============================================================================
start = datetime.now()
merger = DataMerger(processed_data)
merged_data = merger.merge_all()
print(f"Merged in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# FEATURE ENGINEERING
# ============================================================================
start = datetime.now()

risk_matrix = merged_data.get('risk_matrix', pd.DataFrame())
if risk_matrix.empty:
    print("⚠ risk_matrix is empty! Creating from assets...")
    assets = processed_data.get('assets', pd.DataFrame())
    if not assets.empty:
        risk_matrix = assets.copy()
        if 'expected_loss' not in risk_matrix.columns:
            risk_matrix['expected_loss'] = risk_matrix.get('current_risk_score', 5) * 100000
        if 'residual_risk' not in risk_matrix.columns:
            risk_matrix['residual_risk'] = risk_matrix.get('current_risk_score', 5) / 10
        if 'inherent_risk' not in risk_matrix.columns:
            risk_matrix['inherent_risk'] = risk_matrix.get('current_risk_score', 5) / 10
        if 'control_effectiveness' not in risk_matrix.columns:
            risk_matrix['control_effectiveness'] = 0.5
        if 'asset_criticality' not in risk_matrix.columns:
            risk_matrix['asset_criticality'] = risk_matrix.get('criticality_composite', 3)
        merged_data['risk_matrix'] = risk_matrix
        print(f"✅ Created risk_matrix from assets: {risk_matrix.shape}")

engineer = FeatureEngineer(merged_data)
feature_sets = engineer.engineer_all_features(scale=True, select=True)

X_train, X_test, y_train, y_test = engineer.get_train_test_data()

if isinstance(X_train, np.ndarray):
    n_features = X_train.shape[1]
    X_train = pd.DataFrame(X_train, columns=[f'feature_{i}' for i in range(n_features)])
    X_test = pd.DataFrame(X_test, columns=[f'feature_{i}' for i in range(n_features)])

if isinstance(y_train, np.ndarray):
    y_train = pd.Series(y_train, name='target')
if isinstance(y_test, np.ndarray):
    y_test = pd.Series(y_test, name='target')

if X_train is None or len(X_train) == 0:
    print("No features available!")
    sys.exit(1)

print(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
print(f"Features: {X_train.shape[1]}")
print(f"Feature engineering in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# ML MODELS
# ============================================================================
start = datetime.now()
models = CyberRiskModels(config=config.get_all())
model_results = {}
classification_results = None
regression_results = None

# Incremental runs reuse the saved models. Retraining on every refresh would
# dominate the run time without changing the outputs when only risk inputs moved.
if RUN_MODE == 'incremental':
    try:
        models.load_models(str(config.get_models_path()))
        print("Loaded saved models (incremental run — skipping training)")
    except Exception as exc:
        print(f"Could not load saved models ({exc}); falling back to full training")
        RUN_MODE = 'full'

if RUN_MODE == 'full':
    print("\nTraining Classification...")
    y_class_train = (y_train > np.median(y_train)).astype(int)

    classification_results = models.train_classification(
        X_train, y_class_train, epochs=100, batch_size=64
    )
    if classification_results and 'history' in classification_results:
        print("Classification trained")
        model_results['classification'] = classification_results

    print("\nTraining Regression...")
    regression_results = models.train_regression(
        X_train, y_train, epochs=100, batch_size=64
    )
    if regression_results and 'metrics' in regression_results:
        print("Regression trained")
        model_results['regression'] = regression_results

    models.save_models(str(config.get_models_path()))

print(f"ML stage completed in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# FAIR MONTE CARLO - USING REAL DATA
# ============================================================================
start = datetime.now()
print("\n" + "="*60)
print("FAIR MONTE CARLO SIMULATION")
print("="*60)

# Pass the full merged_data to FAIR
fair = FAIRMonteCarlo(merged_data=merged_data, n_iterations=5000)
fair_results = fair.run_simulation("Base", max_assets=500)

if fair_results is not None and not fair_results.empty:
    print(f"✅ FAIR simulation complete: {len(fair_results)} assets analyzed")
else:
    print("⚠ FAIR simulation produced no results")
    fair_results = None

print(f"FAIR in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# WHAT-IF SCENARIO SIMULATION
# ============================================================================
start = datetime.now()
what_if_scenarios = []

if args.skip_scenarios:
    print("\nSkipping what-if scenarios (--skip-scenarios)")
elif fair_results is not None and not fair_results.empty:
    try:
        # Must match the Base simulation's max_assets (500, above). ALE is a
        # portfolio SUM, not an average -- comparing a 500-asset baseline sum
        # against a smaller scenario sum mixes the scenario's real effect with
        # a spurious reduction from summing fewer assets, which previously made
        # every scenario look like a risk reduction regardless of direction.
        fair.run_preset_what_if_scenarios(max_assets=500)
        what_if_scenarios = fair.export_what_if_graph_data()
        print(f"Simulated {len(what_if_scenarios)} what-if scenarios")
    except Exception as exc:
        print(f"What-if simulation failed: {exc}")
else:
    print("\nNo FAIR baseline — skipping what-if scenarios")

print(f"Scenarios in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# BAYESIAN ATTACK GRAPH
# ============================================================================
start = datetime.now()
attack_paths = {}

if args.skip_attack_graph:
    print("\nSkipping attack graph (--skip-attack-graph)")
else:
    try:
        graph_engine = BayesianAttackGraph(
            data={**processed_data, **merged_data},
            config={'max_paths': 20, 'max_assets': 100, 'min_probability': 0.05}
        )
        graph_engine.build_graph()
        graph_engine.find_attack_paths()
        graph_engine.calculate_attack_probabilities()
        critical = graph_engine.identify_critical_paths(top_n=5)
        summary = graph_engine.get_summary()

        attack_paths = {
            'graph_stats': summary.get('graph_stats', {}),
            'total_paths_found': summary.get('attack_paths', {}).get('total_found', 0),
            'top_paths': summary.get('attack_paths', {}).get('top_paths', []),
            'critical_paths': critical if isinstance(critical, dict) else {},
        }
        graph_engine.export_results(str(config.get_output_path('attack_graph_results.json')))
        print(f"Attack graph: {attack_paths['graph_stats'].get('nodes', 0)} nodes, "
              f"{attack_paths['total_paths_found']} paths")
    except Exception as exc:
        print(f"Attack graph analysis failed: {exc}")

print(f"Attack graph in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# INVESTMENT OPTIMIZATION - WITH FIX FOR 100% RISK REDUCTION
# ============================================================================
start = datetime.now()
controls = processed_data.get('security_controls', pd.DataFrame())
frontier_points = []
optimization_result = None

# Get expected_loss
if fair_results is not None and not fair_results.empty:
    if 'expected_ale' in fair_results.columns:
        expected_loss = fair_results['expected_ale'].sum()
    elif 'expected_loss' in fair_results.columns:
        expected_loss = fair_results['expected_loss'].sum()
    else:
        numeric_cols = fair_results.select_dtypes(include=[np.number]).columns
        expected_loss = fair_results[numeric_cols[0]].sum() if len(numeric_cols) > 0 else 10000000
else:
    risk_matrix = merged_data.get('risk_matrix', pd.DataFrame())
    if not risk_matrix.empty and 'expected_loss' in risk_matrix.columns:
        expected_loss = risk_matrix['expected_loss'].sum()
    else:
        expected_loss = 10000000

print(f"\nExpected Annual Loss: ₹{expected_loss:,.2f}")

budget = expected_loss * 0.10
print(f"Investment Budget: ₹{budget:,.2f}")

# ============================================================
# FIX: Combined risk reduction function
# ============================================================
# The optimizer owns this maths. It used to be duplicated here verbatim,
# clamp and all, which is why fixing the flat efficient frontier in
# src/optimization.py changed nothing: the exported frontier was built from
# this copy, not from the method.
def calculate_combined_reduction(selected_controls):
    return optimizer._calculate_combined_reduction(selected_controls)

if not controls.empty:
    # ============================================================
    # Clean and prepare controls
    # ============================================================
    controls_clean = controls.copy()
    
    if 'annual_cost' not in controls_clean.columns:
        if 'implementation_cost' in controls_clean.columns:
            controls_clean['annual_cost'] = controls_clean['implementation_cost']
        elif 'cost' in controls_clean.columns:
            controls_clean['annual_cost'] = controls_clean['cost']
        else:
            controls_clean['annual_cost'] = 500000
    
    # ============================================================
    # FIX: Risk reduction should be between 5% and 40% per control
    # ============================================================
    if 'risk_reduction_percentage' not in controls_clean.columns:
        if 'effectiveness_score' in controls_clean.columns:
            # Convert effectiveness (0-1) to percentage (5-40%)
            controls_clean['risk_reduction_percentage'] = controls_clean['effectiveness_score'] * 40
        elif 'expected_risk_reduction' in controls_clean.columns:
            controls_clean['risk_reduction_percentage'] = controls_clean['expected_risk_reduction']
        else:
            controls_clean['risk_reduction_percentage'] = np.random.uniform(5, 30, len(controls_clean))
    
    # Cap at 40% max for single control (realistic)
    controls_clean['risk_reduction_percentage'] = controls_clean['risk_reduction_percentage'].clip(5, 40)
    
    # Remove controls with no cost or no reduction
    controls_clean = controls_clean[(controls_clean['annual_cost'] > 0) & (controls_clean['risk_reduction_percentage'] > 0)]
    
    print(f"\nControls prepared: {len(controls_clean)} valid controls")
    print(f"Risk reduction range: {controls_clean['risk_reduction_percentage'].min():.1f}% - {controls_clean['risk_reduction_percentage'].max():.1f}%")
    
    if len(controls_clean) > 50:
        controls_sample = controls_clean.head(50)
    else:
        controls_sample = controls_clean
    
    # ============================================================
    # Run optimization
    # ============================================================
    # Pass the whole optimization block so config.json actually drives the
    # model — max_risk_reduction_pct and control_overlap_decay included.
    optimizer = InvestmentOptimizer(
        data=merged_data,
        config=config.get('optimization', {'gordon_loeb_factor': 0.37}),
    )
    
    optimization_result = optimizer.optimize_investment_portfolio(
        controls=controls_sample, budget=budget, expected_loss=expected_loss
    )
    
    # ============================================================
    # Generate efficient frontier with combined reduction
    # ============================================================
    max_budget = min(controls_sample['annual_cost'].sum(), 50000000)
    
    for budget_fraction in np.linspace(0.05, 0.95, 15):
        b = max_budget * budget_fraction
        result = optimizer.solve_knapsack(controls_sample, b)
        
        if result['total_cost'] > 0 and result['selected_items']:
            # Get selected controls and calculate combined reduction
            selected_controls = controls_sample.loc[result['selected_items']]
            total_value = calculate_combined_reduction(selected_controls)
            
            # Calculate ROSI
            rosi = ((expected_loss * (total_value / 100)) - result['total_cost']) / result['total_cost']
            
            # The greedy knapsack's selections are not strictly nested, so a
            # larger budget can occasionally score a hair below a smaller one.
            # Any budget can always afford the cheaper budget's portfolio, so
            # the efficient frontier is non-decreasing by definition — take the
            # running maximum rather than shipping a curve that dips.
            if frontier_points:
                total_value = max(total_value, frontier_points[-1]['risk_reduction'])

            frontier_points.append({
                'budget': result['total_cost'],
                'risk_reduction': total_value,
                'rosi': rosi if rosi > 0 else 0
            })
    
    print("Optimization complete")
else:
    print("⚠ No security controls data available")

print(f"Optimization in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# COMPLIANCE MAPPING
# ============================================================================
start = datetime.now()
compliance_data = processed_data.get('compliance_mapping', pd.DataFrame())
compliance_heatmap = []
compliance_report = None

# No synthetic fallback here by design: a regulatory heatmap built from
# substituted values is worse than no heatmap, because nothing downstream
# can tell the difference. Missing data fails loudly instead.
try:
    if compliance_data is None or compliance_data.empty:
        mapper = ComplianceMapper.from_csv(config.get_data_path('compliance_mapping.csv'))
    else:
        mapper = ComplianceMapper(compliance_data)

    compliance_heatmap = mapper.heatmap_data()

    report_gen = ComplianceReportGenerator(
        mapper, controls=processed_data.get('security_controls', pd.DataFrame())
    )
    compliance_report = report_gen.export(
        json_path=config.get_output_path('compliance_report.json'),
        markdown_path=config.get_output_path('compliance_report.md'),
    )
    print(f"Compliance mapped across {len(compliance_heatmap)} frameworks "
          f"({compliance_report['summary']['total_requirements']} requirements)")
    print("Evidence report: outputs/compliance_report.json + .md")

except ComplianceDataError as exc:
    print(f"\n COMPLIANCE REPORTING SKIPPED: {exc}\n")

print(f"Compliance in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# BUSINESS UNIT / ORGANIZATION ROLLUP
# ============================================================================
start = datetime.now()
business_unit_risk = {}

if fair_results is not None and not fair_results.empty:
    rollup = BusinessUnitRollup(
        fair_results=fair_results,
        assets=processed_data.get('assets', pd.DataFrame()),
        business_units=processed_data.get('business_units', pd.DataFrame()),
        organizations=processed_data.get('organizations', pd.DataFrame()),
    )
    business_unit_risk = rollup.export_graph_data()
    print(f"Rolled up to {len(business_unit_risk.get('by_business_unit', []))} business units, "
          f"{len(business_unit_risk.get('by_organization', []))} organizations")
else:
    print("No FAIR results — skipping business unit rollup")

print(f"Rollup in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# REMEDIATION BACKLOG & PRIORITIZED ACTIONS
# ============================================================================
start = datetime.now()
remediation_data = {}

remediation_df = processed_data.get('remediation_action', pd.DataFrame())
if remediation_df is None or remediation_df.empty:
    remediation_df = raw_data.get('remediation_action', pd.DataFrame())

if remediation_df is not None and not remediation_df.empty:
    planner = RemediationPlanner(remediation_df, assets=processed_data.get('assets', pd.DataFrame()))
    remediation_data = planner.export_graph_data(limit=25)
    backlog = remediation_data.get('backlog', {})
    print(f"Remediation: {backlog.get('open_actions', 0)} open of {backlog.get('total_actions', 0)}, "
          f"₹{backlog.get('open_loss_reduction_available', 0):,.0f} loss reduction available")
else:
    print("No remediation_actions data available")

print(f"Remediation in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# RISK TREND SNAPSHOT
# ============================================================================
start = datetime.now()

history = RiskHistory(config.get_output_path('risk_history.json'))

_ctrl_eff = 0.0
if fair_results is not None and not fair_results.empty and 'control_effectiveness' in fair_results.columns:
    _ctrl_eff = float(fair_results['control_effectiveness'].mean())

_compliance_pct = 0.0
if compliance_heatmap:
    _compliance_pct = float(np.mean([f['compliant'] for f in compliance_heatmap]))

_open_vulns = 0
_vulns = processed_data.get('vulnerabilities', pd.DataFrame())
if not _vulns.empty and 'status' in _vulns.columns:
    _open_vulns = int((_vulns['status'].astype(str).str.lower() != 'closed').sum())

_annual_revenue = 0.0
_orgs = processed_data.get('organizations', pd.DataFrame())
if not _orgs.empty and 'annual_revenue' in _orgs.columns:
    _annual_revenue = float(pd.to_numeric(_orgs['annual_revenue'], errors='coerce').fillna(0).sum())

snapshot = history.append(
    expected_annual_loss=fair_results['expected_ale'].sum() if fair_results is not None and not fair_results.empty else 0,
    var_95=fair_results['var_95'].sum() if fair_results is not None and not fair_results.empty else 0,
    var_99=fair_results['var_99'].sum() if fair_results is not None and not fair_results.empty else 0,
    assets_simulated=int(len(fair_results)) if fair_results is not None else 0,
    open_vulnerabilities=_open_vulns,
    avg_control_effectiveness=_ctrl_eff,
    compliance_pct=_compliance_pct,
    annual_revenue=_annual_revenue,
    run_mode=RUN_MODE,
)
trend = history.trend_data(limit=60)
print(f"Risk snapshot recorded — Enterprise Risk Score {snapshot['enterprise_risk_score']}, "
      f"trend {trend['direction']} ({trend['points']} points)")
print(f"Trend in {(datetime.now() - start).total_seconds():.1f}s")

# ============================================================================
# EXPORT GRAPH DATA
# ============================================================================
print("\nExporting graph data...")

training_data = []
if classification_results and 'history' in classification_results:
    history = classification_results['history']
    for epoch in range(len(history.history['loss'])):
        training_data.append({
            'epoch': epoch + 1,
            'loss': round(float(history.history['loss'][epoch]), 4),
            'val_loss': round(float(history.history['val_loss'][epoch]), 4),
            'accuracy': round(float(history.history['accuracy'][epoch]), 4),
            'val_accuracy': round(float(history.history['val_accuracy'][epoch]), 4)
        })

classification_metrics = []
if classification_results and 'metrics' in classification_results:
    metrics = classification_results['metrics']
    classification_metrics = [
        {'metric': 'Accuracy', 'value': round(metrics.get('accuracy', 0) * 100, 2)},
        {'metric': 'Precision', 'value': round(metrics.get('precision', 0) * 100, 2)},
        {'metric': 'Recall', 'value': round(metrics.get('recall', 0) * 100, 2)},
        {'metric': 'F1 Score', 'value': round(metrics.get('f1', 0) * 100, 2)},
        {'metric': 'ROC-AUC', 'value': round(metrics.get('roc_auc', 0) * 100, 2)}
    ]

confusion_matrix_data = []
if classification_results and 'confusion_matrix' in classification_results:
    cm = classification_results['confusion_matrix']
    class_names = ['No Incident', 'Incident']
    for i, row in enumerate(cm):
        for j, val in enumerate(row):
            confusion_matrix_data.append({
                'actual': class_names[i],
                'predicted': class_names[j],
                'value': int(val)
            })

regression_metrics = []
if regression_results and 'metrics' in regression_results:
    metrics = regression_results['metrics']
    regression_metrics = [
        {'metric': 'R²', 'value': round(metrics.get('r2', 0), 4)},
        {'metric': 'MAE', 'value': round(metrics.get('mae', 0), 2)},
        {'metric': 'RMSE', 'value': round(metrics.get('rmse', 0), 2)},
        {'metric': 'MAPE (%)', 'value': round(metrics.get('mape', 0), 2)}
    ]

loss_distribution = []
if fair_results is not None and not fair_results.empty:
    ale_dist = fair.ale_distributions.get('Base', np.array([]))
    if len(ale_dist) > 0:
        hist, bin_edges = np.histogram(ale_dist, bins=20)
        for i in range(len(hist)):
            loss_distribution.append({
                'loss_bin': f'{(bin_edges[i]/1e6):.0f}M-{(bin_edges[i+1]/1e6):.0f}M',
                'frequency': int(hist[i])
            })

var_curve = []
if fair_results is not None and not fair_results.empty:
    ale_dist = fair.ale_distributions.get('Base', np.array([]))
    if len(ale_dist) > 0:
        sorted_ales = np.sort(ale_dist)[::-1]
        exceedance_prob = np.arange(1, len(sorted_ales) + 1) / len(sorted_ales)
        step = max(1, len(sorted_ales) // 80)
        for i in range(0, len(sorted_ales), step):
            var_curve.append({
                'loss': round(float(sorted_ales[i]), 0),
                'exceedance_prob': round(float(exceedance_prob[i]), 4)
            })
        var_95 = np.percentile(ale_dist, 95)
        var_99 = np.percentile(ale_dist, 99)
        var_curve.append({'loss': round(float(var_95), 0), 'exceedance_prob': 0.05, 'label': 'VaR 95%'})
        var_curve.append({'loss': round(float(var_99), 0), 'exceedance_prob': 0.01, 'label': 'VaR 99%'})

efficient_frontier = []
for point in frontier_points:
    efficient_frontier.append({
        'investment': round(float(point['budget']), 0),
        'risk_reduction': round(float(point['risk_reduction']), 2),
        'rosi': round(float(point['rosi']), 2)
    })
if optimization_result:
    efficient_frontier.append({
        'investment': round(float(optimization_result.get('total_investment', 0)), 0),
        'risk_reduction': round(float(optimization_result.get('total_risk_reduction', 0)), 2),
        'rosi': round(float(optimization_result.get('rosi', 0)), 2),
        'is_optimal': True
    })

rosi_per_control = []
if optimization_result and 'selected_details' in optimization_result:
    selected = optimization_result['selected_details']
    if isinstance(selected, pd.DataFrame):
        for _, item in selected.iterrows():
            rosi_per_control.append({
                'control_id': str(item.get('control_id', '')),
                'control_name': str(item.get('control_name', f'Control_{item["control_id"]}'))[:20],
                'cost': round(float(item.get('annual_cost', 0)), 0),
                'risk_reduction': round(float(item.get('risk_reduction', 0)), 2)
            })

executive_summary = {}
if fair_results is not None and not fair_results.empty:
    ale_dist = fair.ale_distributions.get('Base', np.array([]))
    if len(ale_dist) > 0:
        if 'expected_ale' in fair_results.columns:
            total_loss = fair_results['expected_ale'].sum()
        elif 'expected_loss' in fair_results.columns:
            total_loss = fair_results['expected_loss'].sum()
        elif 'expected_annual_loss' in fair_results.columns:
            total_loss = fair_results['expected_annual_loss'].sum()
        else:
            numeric_cols = fair_results.select_dtypes(include=[np.number]).columns
            total_loss = fair_results[numeric_cols[0]].sum() if len(numeric_cols) > 0 else 0
        
        executive_summary['total_expected_loss'] = round(float(total_loss), 0)
        executive_summary['var_95'] = round(float(np.percentile(ale_dist, 95)), 0)
        executive_summary['var_99'] = round(float(np.percentile(ale_dist, 99)), 0)
        # Per-asset mean, not the mean of the portfolio distribution (which is
        # just total expected loss again).
        executive_summary['avg_ale'] = round(
            float(fair.get_risk_metrics().get('avg_ale', 0)), 0)
        executive_summary['assets_simulated'] = int(len(fair_results))

executive_summary['enterprise_risk_score'] = snapshot['enterprise_risk_score']
executive_summary['risk_trend_direction'] = trend['direction']

if optimization_result:
    executive_summary['total_investment'] = round(float(optimization_result.get('total_investment', 0)), 0)
    executive_summary['risk_reduction'] = round(float(optimization_result.get('total_risk_reduction', 0)), 2)
    executive_summary['rosi'] = round(float(optimization_result.get('rosi', 0)), 2)
    
if classification_results and 'metrics' in classification_results:
    executive_summary['model_accuracy'] = round(classification_results['metrics'].get('accuracy', 0) * 100, 2)
    
if regression_results and 'metrics' in regression_results:
    executive_summary['model_r2'] = round(regression_results['metrics'].get('r2', 0), 4)

asset_risk_scores = []
if 'risk_matrix' in merged_data and not merged_data['risk_matrix'].empty:
    risk_df = merged_data['risk_matrix']
    if 'asset_id' in risk_df.columns and 'residual_risk' in risk_df.columns:
        top_risks = risk_df.nlargest(10, 'residual_risk')[['asset_id', 'residual_risk']]
        for _, row in top_risks.iterrows():
            asset_risk_scores.append({
                'asset_id': str(row['asset_id']),
                'risk_score': round(float(row['residual_risk']), 3)
            })

severity_counts = []
if processed_data and 'vulnerabilities' in processed_data:
    vuln = processed_data['vulnerabilities']
    if not vuln.empty and 'severity' in vuln.columns:
        counts = vuln['severity'].value_counts()
        severity_map = {'Critical': 'Critical', 'High': 'High', 'Medium': 'Medium', 'Low': 'Low'}
        for severity, count in counts.items():
            severity_counts.append({
                'severity': severity_map.get(severity, severity),
                'count': int(count)
            })

control_effectiveness = []
if processed_data and 'security_controls' in processed_data:
    controls_df = processed_data['security_controls']
    if not controls_df.empty and 'effectiveness_score' in controls_df.columns:
        top_controls = controls_df.nlargest(10, 'effectiveness_score')
        for _, row in top_controls.iterrows():
            control_effectiveness.append({
                'control_name': str(row.get('control_name', row.get('control_id', 'Control')))[:25],
                'effectiveness': round(float(row['effectiveness_score']) * 100, 1)
            })

all_graph_data = {
    'training_curves': training_data,
    'classification_metrics': classification_metrics,
    'confusion_matrix': confusion_matrix_data,
    'regression_metrics': regression_metrics,
    'loss_distribution': loss_distribution,
    'var_curve': var_curve,
    'efficient_frontier': efficient_frontier,
    'rosi_per_control': rosi_per_control,
    'compliance_heatmap': compliance_heatmap,
    'business_unit_risk': business_unit_risk,
    'what_if_scenarios': what_if_scenarios,
    'attack_paths': attack_paths,
    'remediation': remediation_data,
    'live_devices': {'count': live_device_count},
    'risk_trend': trend['risk_trend'],
    'financial_exposure_trend': trend['financial_exposure_trend'],
    'trend_summary': {
        'direction': trend['direction'],
        'change_pct': trend['change_pct'],
        'points': trend['points'],
    },
    'executive_summary': executive_summary,
    'asset_risk_scores': asset_risk_scores,
    'severity_counts': severity_counts,
    'control_effectiveness': control_effectiveness,
    'metadata': {
        'generated_at': datetime.now().isoformat(),
        'run_mode': RUN_MODE,
        'total_assets': len(processed_data.get('assets', [])),
        'total_vulnerabilities': len(processed_data.get('vulnerabilities', [])),
        'total_controls': len(processed_data.get('security_controls', [])),
        'total_incidents': len(processed_data.get('security_incidents', []))
    }
}

# An incremental run doesn't retrain, so it has no fresh training curves or
# model metrics. Carry the previous run's values forward rather than emitting
# empty arrays that would blank those panels on the dashboard.
if RUN_MODE == 'incremental' and os.path.exists('outputs/graph_data.json'):
    try:
        with open('outputs/graph_data.json') as f:
            previous = json.load(f)
        for key in ('training_curves', 'classification_metrics', 'confusion_matrix', 'regression_metrics'):
            if not all_graph_data[key] and previous.get(key):
                all_graph_data[key] = previous[key]
                all_graph_data['metadata'].setdefault('carried_forward', []).append(key)
    except (json.JSONDecodeError, OSError):
        pass

with open('outputs/graph_data.json', 'w') as f:
    json.dump(all_graph_data, f, indent=2)

print(f"\nGraph data exported to outputs/graph_data.json")

AuditLog(config.get_output_path('audit_log.jsonl')).record(
    action='pipeline_run',
    actor='cli',
    detail={
        'mode': RUN_MODE,
        'assets_simulated': int(len(fair_results)) if fair_results is not None else 0,
        'scenarios': len(what_if_scenarios),
        'attack_paths': attack_paths.get('total_paths_found', 0),
        'frameworks': len(compliance_heatmap),
    },
)

total_time = (datetime.now() - start_total).total_seconds()

print("\n" + "="*80)
print(f"Complete in {total_time:.1f}s")
print("="*80)
print("\nGraph Data Exported:")
print("="*60)
print(f"  1. Training Curves: {len(training_data)} points")
print(f"  2. Classification Metrics: {len(classification_metrics)}")
print(f"  3. Confusion Matrix: {len(confusion_matrix_data)}")
print(f"  4. Regression Metrics: {len(regression_metrics)}")
print(f"  5. Loss Distribution: {len(loss_distribution)} bins")
print(f"  6. VaR Curve: {len(var_curve)} points")
print(f"  7. Efficient Frontier: {len(efficient_frontier)} points")
print(f"  8. ROSI per Control: {len(rosi_per_control)}")
print(f"  9. Compliance Heatmap: {len(compliance_heatmap)} frameworks")
print(f" 11. Business Units: {len(business_unit_risk.get('by_business_unit', []))}")
print(f" 12. Organizations: {len(business_unit_risk.get('by_organization', []))}")
print(f" 13. What-If Scenarios: {len(what_if_scenarios)}")
print(f" 14. Attack Paths: {attack_paths.get('total_paths_found', 0)}")
print(f" 15. Remediation Actions: {remediation_data.get('backlog', {}).get('open_actions', 0)} open")
print(f" 16. Risk Trend: {trend['points']} points ({trend['direction']})")
print(f" 17. Enterprise Risk Score: {snapshot['enterprise_risk_score']}")
print(f"  10. Executive Summary: {len(executive_summary)} metrics")
print("="*60)
print(f"\nOutput: outputs/graph_data.json")
print("="*80)