"""
Machine Learning Models  
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List, Tuple
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, r2_score, mean_absolute_error, mean_squared_error,
    confusion_matrix, explained_variance_score, classification_report
)
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks
import joblib
from pathlib import Path
import warnings
import os
warnings.filterwarnings('ignore')

np.random.seed(42)
tf.random.set_seed(42)


class CyberRiskModels:
    """Pure TensorFlow Implementation - Scikit-Learn Compatible API"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.models = {}
        self.results = {}
        self.scalers = {}
        self.best_models = {}
        self.best_model_names = {}
        self.feature_importance = {}
        self.config = config or {}
        self.epochs = 100  
        self.histories = {}
    
    def _prepare_data(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        """
        Prepare data - numeric only, no NaN, no inf
        Handles both pandas DataFrame and numpy array inputs
        """
        # ============================================================
        # FIX: Handle numpy arrays by converting to DataFrame
        # This allows the model to work with both DataFrame and numpy
        # ============================================================
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X)
        
        if isinstance(y, np.ndarray):
            y = pd.Series(y)
        
        X_clean = X.select_dtypes(include=[np.number]).copy()
        X_clean = X_clean.fillna(0).replace([np.inf, -np.inf], 0)
         
        if X_clean.shape[1] > 0:
            std_cols = X_clean.std()
            X_clean = X_clean.loc[:, (std_cols > 0.001) | (std_cols == 0)]
        
        if y is not None:
            if isinstance(y, np.ndarray):
                y = pd.Series(y)
            y_clean = y.fillna(0).replace([np.inf, -np.inf], 0)
            return X_clean, y_clean
        
        return X_clean, None
    
    def _build_classifier(self, input_dim: int) -> keras.Model:
        """Build TensorFlow classifier model"""
        model = keras.Sequential([
            layers.Dense(128, activation='relu', input_shape=(input_dim,)),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(32, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.2),
            
            layers.Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', 'precision', 'recall', 'auc']
        )
        
        return model
    
    def _build_regressor(self, input_dim: int) -> keras.Model:
        """Build TensorFlow regressor model"""
        model = keras.Sequential([
            layers.Dense(128, activation='relu', input_shape=(input_dim,)),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(32, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.2),
            
            layers.Dense(1, activation='linear')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae', 'mse']
        )
        
        return model
    
    def train_classification(self, X: pd.DataFrame, y: pd.Series,
                            model_type: str = 'tensorflow',
                            test_size: float = 0.2,
                            epochs: int = 100,
                            batch_size: int = 32) -> Dict[str, Any]:
        """Train TensorFlow classification model for incident prediction"""
        print(f"\n Classification:")
        print(f"   Samples: {X.shape[0]}, Features: {X.shape[1]}")
        print(f"   Epochs: {epochs}, Batch Size: {batch_size}")
        
        X_clean, y_clean = self._prepare_data(X, y)
        
        if X_clean.shape[1] == 0:
            print("   ⚠ No numeric features available")
            return {}
         
        class_counts = y_clean.value_counts()
        print(f"   Class distribution: {dict(class_counts)}")
        
        if len(class_counts) < 2:
            print("   ⚠ Only one class present! Cannot train classifier.")
            return {}
         
        min_class = class_counts.min()
        total_samples = len(y_clean)
        imbalance_ratio = min_class / total_samples
        
        if imbalance_ratio < 0.05:
            print(f"   ⚠ Severe class imbalance: {min_class} samples ({imbalance_ratio*100:.1f}%)")
            print("   Using class weights for handling imbalance")
         
        from sklearn.utils.class_weight import compute_class_weight
        class_weights = compute_class_weight('balanced', classes=np.unique(y_clean), y=y_clean)
        class_weight_dict = dict(zip(np.unique(y_clean), class_weights))
        print(f"   Class weights: {class_weight_dict}")
         
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X_clean, y_clean, test_size=test_size, random_state=42, stratify=y_clean
            )
        except ValueError:
            print("   ⚠ Stratification failed, using regular split")
            X_train, X_test, y_train, y_test = train_test_split(
                X_clean, y_clean, test_size=test_size, random_state=42
            )
        
        print(f"   Train: {X_train.shape[0]} (Class 0: {sum(y_train==0)}, Class 1: {sum(y_train==1)})")
        print(f"   Test: {X_test.shape[0]} (Class 0: {sum(y_test==0)}, Class 1: {sum(y_test==1)})")
         
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers['classification'] = scaler
         
        model = self._build_classifier(X_train_scaled.shape[1])
         
        early_stopping = callbacks.EarlyStopping(
            monitor='val_loss', patience=20, restore_best_weights=True
        )
        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=10, min_lr=1e-6
        )
         
        print("   Training model...")
        history = model.fit(
            X_train_scaled, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[early_stopping, reduce_lr],
            class_weight=class_weight_dict,
            verbose=0
        )
         
        self.histories['classification'] = history
         
        y_proba = model.predict(X_test_scaled, verbose=0).flatten()
        y_pred = (y_proba > 0.5).astype(int)
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_test, y_proba)
        }
         
        weights = model.layers[0].get_weights()[0]
        importance = np.abs(weights).mean(axis=1)
        self.feature_importance['classification'] = pd.DataFrame({
            'feature': X_clean.columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
         
        self.best_models['classification'] = model
        self.best_model_names['classification'] = 'tensorflow'
        self.results['classification'] = {
            'model': model,
            'metrics': metrics,
            'history': history,
            'feature_names': X_clean.columns.tolist(),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'classification_report': classification_report(y_test, y_pred, output_dict=True),
            'y_test': y_test,
            'y_pred': y_pred,
            'y_proba': y_proba,
            'X_test': X_test,
            'epochs_trained': len(history.history['loss'])
        }
        
        print(f"\n    Classification Results:")
        print(f"      Accuracy: {metrics['accuracy']*100:.2f}%")
        print(f"      Precision: {metrics['precision']*100:.2f}%")
        print(f"      Recall: {metrics['recall']*100:.2f}%")
        print(f"      F1 Score: {metrics['f1']*100:.2f}%")
        print(f"      ROC-AUC: {metrics['roc_auc']*100:.2f}%")
        print(f"      Epochs trained: {len(history.history['loss'])}")
        
        return self.results['classification']
    
    def train_regression(self, X: pd.DataFrame, y: pd.Series,
                        model_type: str = 'tensorflow',
                        test_size: float = 0.2,
                        epochs: int = 100,
                        batch_size: int = 32) -> Dict[str, Any]:
        """Train TensorFlow regression model for ALE prediction"""
        print(f"\n Regression: TENSORFLOW")
        print(f"   Samples: {X.shape[0]}, Features: {X.shape[1]}")
        print(f"   Epochs: {epochs}, Batch Size: {batch_size}")
        
        X_clean, y_clean = self._prepare_data(X, y)
        
        if X_clean.shape[1] == 0:
            print("   ⚠ No numeric features available")
            return {}
         
        print(f"   Target range: {y_clean.min():.2f} - {y_clean.max():.2f}")
        print(f"   Target skew: {y_clean.skew():.2f}")
         
        skew = y_clean.skew()
        use_log = skew > 2
        if use_log:
            y_trans = np.log1p(y_clean + 1)
            print(f"   Log transform applied (skew: {skew:.2f} -> {y_trans.skew():.2f})")
        else:
            y_trans = y_clean
         
        X_train, X_test, y_train, y_test = train_test_split(
            X_clean, y_trans, test_size=test_size, random_state=42
        )
        
        print(f"   Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")
         
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers['regression'] = scaler
         
        y_scaler = StandardScaler()
        y_train_scaled = y_scaler.fit_transform(y_train.values.reshape(-1, 1)).flatten()
         
        model = self._build_regressor(X_train_scaled.shape[1])
         
        early_stopping = callbacks.EarlyStopping(
            monitor='val_loss', patience=20, restore_best_weights=True
        )
        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=10, min_lr=1e-6
        )
        print("   Training TensorFlow model...")
        history = model.fit(
            X_train_scaled, y_train_scaled,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            callbacks=[early_stopping, reduce_lr],
            verbose=0
        )
         
        self.histories['regression'] = history
         
        y_pred_scaled = model.predict(X_test_scaled, verbose=0).flatten()
        y_pred = y_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
         
        if use_log:
            y_pred = np.expm1(y_pred) - 1
            y_test_orig = np.expm1(y_test) - 1
        else:
            y_test_orig = y_test
         
        metrics = {
            'r2': r2_score(y_test_orig, y_pred),
            'mae': mean_absolute_error(y_test_orig, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test_orig, y_pred)),
            'explained_variance': explained_variance_score(y_test_orig, y_pred)
        }
         
        non_zero = y_test_orig != 0
        if np.any(non_zero):
            try:
                metrics['mape'] = np.mean(np.abs((y_test_orig[non_zero] - y_pred[non_zero]) / y_test_orig[non_zero])) * 100
            except:
                pass
         
        residuals = y_test_orig - y_pred
        metrics['residual_mean'] = residuals.mean()
        metrics['residual_std'] = residuals.std()
        metrics['residual_skew'] = residuals.skew()
         
        weights = model.layers[0].get_weights()[0]
        importance = np.abs(weights).mean(axis=1)
        self.feature_importance['regression'] = pd.DataFrame({
            'feature': X_clean.columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
         
        self.best_models['regression'] = model
        self.best_model_names['regression'] = 'tensorflow'
        self.results['regression'] = {
            'model': model,
            'metrics': metrics,
            'history': history,
            'residuals': residuals,
            'feature_names': X_clean.columns.tolist(),
            'y_test': y_test_orig,
            'y_pred': y_pred,
            'X_test': X_test,
            'used_log_transform': use_log,
            'epochs_trained': len(history.history['loss']),
            'y_scaler': y_scaler
        }
        
        print(f"\n    Regression Results:")
        print(f"      R²: {metrics['r2']:.4f}")
        print(f"      MAE: {metrics['mae']:.2f}")
        print(f"      RMSE: {metrics['rmse']:.2f}")
        if 'mape' in metrics:
            print(f"      MAPE: {metrics['mape']:.2f}%")
        print(f"      Explained Variance: {metrics['explained_variance']:.4f}")
        print(f"      Epochs trained: {len(history.history['loss'])}")
        
        return self.results['regression']
    
    def train_risk_quantification(self, X: pd.DataFrame, y: pd.Series,
                                  epochs: int = 100,
                                  batch_size: int = 32,
                                  validation_split: float = 0.2) -> Dict[str, Any]:
        """Risk quantification model (regression wrapper)"""
        print(f"\n Risk Quantification (TensorFlow)")
        return self.train_regression(
            X, y, 
            test_size=validation_split, 
            epochs=epochs, 
            batch_size=batch_size
        )
    
    def predict_classification(self, X: pd.DataFrame) -> np.ndarray:
        """Predict incident probability"""
        if 'classification' not in self.best_models:
            raise ValueError("Classification model not trained")
        X_clean, _ = self._prepare_data(X)
        X_scaled = self.scalers['classification'].transform(X_clean)
        model = self.best_models['classification']
        return model.predict(X_scaled, verbose=0).flatten()
    
    def predict_regression(self, X: pd.DataFrame) -> np.ndarray:
        """Predict ALE"""
        if 'regression' not in self.best_models:
            raise ValueError("Regression model not trained")
        X_clean, _ = self._prepare_data(X)
        X_scaled = self.scalers['regression'].transform(X_clean)
        y_pred_scaled = self.best_models['regression'].predict(X_scaled, verbose=0).flatten()
         
        if 'regression' in self.results and 'y_scaler' in self.results['regression']:
            y_scaler = self.results['regression']['y_scaler']
            y_pred = y_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
             
            if self.results['regression'].get('used_log_transform', False):
                y_pred = np.expm1(y_pred) - 1
            return y_pred
        
        return y_pred_scaled
    
    def get_feature_importance(self, model_type: str = 'classification') -> pd.DataFrame:
        """Get feature importance DataFrame"""
        return self.feature_importance.get(model_type, pd.DataFrame({'feature': [], 'importance': []}))
    
    def get_best_model(self, model_type: str = 'classification'):
        """Get best trained model"""
        return self.best_models.get(model_type)
    
    def get_results(self, model_type: str = 'classification') -> Dict:
        """Get training results"""
        return self.results.get(model_type, {})
    
    def get_history(self, model_type: str = 'classification'):
        """Get training history"""
        return self.histories.get(model_type)
    
    def save_models(self, path: str = 'models/'):
        """Save all models to disk"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        for model_type, model in self.best_models.items():
            try:
                model.save(path / f"{model_type}_model.keras")
                print(f"  ✓ Saved {model_type} model")
            except Exception as e:
                print(f"  ✗ Failed to save {model_type} model: {e}")

        try:
            joblib.dump(self.scalers, path / "scalers.pkl")
            print(f"  ✓ Saved scalers")
        except Exception as e:
            print(f"  ✗ Failed to save scalers: {e}")

        try:
            joblib.dump(self.best_model_names, path / "best_model_names.pkl")
            print(f"  ✓ Saved model names")
        except Exception as e:
            print(f"  ✗ Failed to save model names: {e}")

        print(f"   All models saved to {path}")

    def load_models(self, path: str = 'models/'):
        """
        Load all models from disk.

        Raises FileNotFoundError if no model could be loaded — callers running
        in incremental mode rely on that to fall back to full training rather
        than continuing with an empty model set.
        """
        path = Path(path)
        loaded = []

        for model_type in ['classification', 'regression']:
            model_file = path / f"{model_type}_model.keras"
            try:
                self.best_models[model_type] = keras.models.load_model(model_file)
                loaded.append(model_type)
                print(f"  ✓ Loaded {model_type} model")
            except Exception as e:
                print(f"  ✗ Failed to load {model_type} model: {e}")

        if not loaded:
            raise FileNotFoundError(
                f"No usable models found in {path}. Run `python main.py --mode full` first."
            )

        try:
            self.scalers = joblib.load(path / "scalers.pkl")
            print(f"  ✓ Loaded scalers")
        except Exception as e:
            print(f"  ✗ Failed to load scalers: {e}")

        try:
            self.best_model_names = joblib.load(path / "best_model_names.pkl")
            print(f"  ✓ Loaded model names")
        except Exception as e:
            print(f"  ✗ Failed to load model names: {e}")

        print(f"   Models loaded from {path}: {', '.join(loaded)}")
        return loaded
    
    def train_all_models(self, X_class: pd.DataFrame, y_class: pd.Series,
                         X_reg: pd.DataFrame, y_reg: pd.Series,
                         epochs: int = 100,
                         batch_size: int = 32) -> Dict:
        """Train all models"""
        print("\n" + "="*60)
        print("TRAINING MODELS")
        print("="*60)
        print(f"Epochs: {epochs}, Batch Size: {batch_size}")
        
        results = {}
         
        print("\nCLASSIFICATION MODEL:")
        class_counts = y_class.value_counts()
        print(f"   Class distribution: {dict(class_counts)}")
        
        if len(class_counts) >= 2 and class_counts.min() >= 5:
            try:
                result = self.train_classification(
                    X_class, y_class,
                    epochs=epochs,
                    batch_size=batch_size,
                    test_size=0.2
                )
                if result:
                    results['classification'] = result
            except Exception as e:
                print(f"   ✗ Classification failed: {e}")
        else:
            print("   ⚠ Not enough data for classification (need at least 5 samples per class)")
         
        print("\nREGRESSION MODEL:")
        try:
            result = self.train_regression(
                X_reg, y_reg,
                epochs=epochs,
                batch_size=batch_size,
                test_size=0.2
            )
            if result:
                results['regression'] = result
        except Exception as e:
            print(f"   ✗ Regression failed: {e}")
        
        return results
    
    def evaluate_model(self, model_type: str = 'classification'):
        """Evaluate trained model and print detailed metrics"""
        if model_type not in self.results:
            print(f"⚠ No results found for {model_type}")
            return
        
        results = self.results[model_type]
        metrics = results.get('metrics', {})
        
        print(f"\n {model_type.upper()} Model Evaluation")
        print("="*40)
        
        if model_type == 'classification':
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    if key in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
                        print(f"  {key}: {value*100:.2f}%")
                    else:
                        print(f"  {key}: {value:.4f}")
        else:
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    if key in ['mape']:
                        print(f"  {key}: {value:.2f}%")
                    else:
                        print(f"  {key}: {value:.4f}")
        
        if 'confusion_matrix' in results:
            cm = np.array(results['confusion_matrix'])
            print(f"\n  Confusion Matrix:")
            print(f"    [[{cm[0][0]:>5} {cm[0][1]:>5}]]")
            print(f"    [[{cm[1][0]:>5} {cm[1][1]:>5}]]")
        
        if 'classification_report' in results:
            report = results['classification_report']
            print(f"\n  Classification Report:")
            for class_label, metrics_dict in report.items():
                if class_label not in ['accuracy', 'macro avg', 'weighted avg']:
                    print(f"    Class {class_label}:")
                    print(f"      Precision: {metrics_dict.get('precision', 0)*100:.2f}%")
                    print(f"      Recall: {metrics_dict.get('recall', 0)*100:.2f}%")
                    print(f"      F1: {metrics_dict.get('f1-score', 0)*100:.2f}%")
         
        history = self.get_history(model_type)
        if history:
            print(f"\n  Training History:")
            print(f"    Final Loss: {history.history['loss'][-1]:.4f}")
            print(f"    Final Val Loss: {history.history['val_loss'][-1]:.4f}")
            print(f"    Epochs completed: {len(history.history['loss'])}/{results.get('epochs_trained', 'N/A')}")
    
    def get_config(self):
        """Get current configuration"""
        return self.config
    
    def set_epochs(self, epochs: int):
        """Set epochs for training"""
        self.epochs = epochs


class RiskMLModels(CyberRiskModels):
    """Alias for backward compatibility"""
    pass


class RiskMLModel(CyberRiskModels):
    """Alias for backward compatibility"""
    pass