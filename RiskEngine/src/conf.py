"""
Configuration Manager 
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Config: 
    
    _instance = None
    _config = None
    _config_path = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: str = "config.json"): 
        possible_paths = [
            Path(config_path),
            Path(__file__).parent.parent / config_path,
            Path(__file__).parent / config_path,
            Path.cwd() / config_path,
            Path.cwd() / "config" / config_path
        ]
        
        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        self._config = json.load(f)
                    self._config_path = str(path)
                    print(f"Loaded config from: {path}")
                    return
                except json.JSONDecodeError as e:
                    print(f"⚠ Error parsing config file {path}: {e}")
                except Exception as e:
                    print(f"⚠ Error loading config from {path}: {e}")
         
        print("⚠ No config file found. Using default configuration.")
        self._config = self._default_config()
        self._save_default_config(config_path)
    
    def _save_default_config(self, config_path: str = "config.json"): 
        try: 
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            print(f"Created default config at: {config_path}")
        except Exception as e:
            print(f"⚠ Could not save default config: {e}")
    
    def _default_config(self) -> Dict[str, Any]: 
        return { 
            "data_path": "./data/",
            "output_path": "./outputs/",
            "models_path": "./models/",
            "logs_path": "./logs/",
             
            "data_files": {
                "assets": "assets.csv",
                "vulnerabilities": "vulnerabilities.csv",
                "security_controls": "security_controls.csv",
                "business_impact": "business_impact.csv",
                "security_incidents": "security_incidents.csv",
                "threat_intelligence": "threat_intelligence.csv",
                "compliance_mapping": "compliance_mapping.csv"
            },
             
            "ml_models": {
                "classification": {
                    "epochs": 100,
                    "batch_size": 32,
                    "test_size": 0.2,
                    "early_stopping_patience": 20
                },
                "regression": {
                    "epochs": 100,
                    "batch_size": 32,
                    "test_size": 0.2,
                    "early_stopping_patience": 20
                },
                "risk_quantification": {
                    "epochs": 150,
                    "batch_size": 64,
                    "test_size": 0.2,
                    "early_stopping_patience": 30
                }
            },
             
            "simulation": {
                "iterations": 10000,
                "confidence_levels": [0.95, 0.99],
                "max_assets": 500
            },
             
            "optimization": {
                "budget_percentage": 0.10,
                "gordon_loeb_factor": 0.37,
                "max_risk_reduction_pct": 85.0,
                "control_overlap_decay": 0.9,
                "max_controls": 20
            },
             
            "attack_graph": {
                "max_paths": 20,
                "path_cutoff": 3,
                "min_probability": 0.01,
                "max_assets": 100
            },
             
            "dashboard": {
                "max_query_history": 50,
                "export_format": "json",
                "plot_dpi": 150
            },
             
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "file": "platform.log"
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
         
        if self._config is None:
            self.load_config()
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        
        if self._config is None:
            self.load_config()
        
        keys = key.split('.')
        target = self._config
        
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
    
    def get_data_path(self, filename: Optional[str] = None) -> Path:
        
        data_path = Path(self.get('data_path', './data/'))
        if filename:
            return data_path / filename
        return data_path
    
    def get_output_path(self, filename: Optional[str] = None) -> Path:
        
        output_path = Path(self.get('output_path', './outputs/'))
        if filename:
            return output_path / filename
        return output_path
    
    def get_models_path(self, filename: Optional[str] = None) -> Path:
        
        models_path = Path(self.get('models_path', './models/'))
        if filename:
            return models_path / filename
        return models_path
    
    def get_all(self) -> Dict[str, Any]:
       
        return self._config
    
    def update(self, updates: Dict[str, Any]):
         
        def _update_recursive(d, u):
            for k, v in u.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    _update_recursive(d[k], v)
                else:
                    d[k] = v
        
        if self._config is None:
            self.load_config()
        
        _update_recursive(self._config, updates)
    
    def save(self, config_path: Optional[str] = None):
        
        if self._config is None:
            return
        
        path = config_path or self._config_path or "config.json"
        
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self._config, f, indent=2)
            print(f"✅ Configuration saved to: {path}")
        except Exception as e:
            print(f"⚠ Could not save configuration: {e}")
    
    def reload(self): 
        if self._config_path:
            self.load_config(self._config_path)
        else:
            self.load_config()
    
    def __repr__(self):
        return f"Config(path={self._config_path}, loaded={self._config is not None})"
    
    def __str__(self):
        return json.dumps(self._config, indent=2)

 

config = Config()

 

def get_config(key: str = None, default: Any = None) -> Any:
     
    if key is None:
        return config.get_all()
    return config.get(key, default)


def update_config(updates: Dict[str, Any]):
    
    config.update(updates)
    config.save()


def reset_config(): 
    config._config = config._default_config()
    config.save()

 

class ConfigManager: 
    def __new__(cls):
        return config 