# ml/__init__.py

from .model import PricePredictionModel, RestockPredictor
from .dataset import DatasetPreparator 
from .trainer import ModelTrainer

import logging
import torch
from pathlib import Path

# Logger Setup
logger = logging.getLogger("ML")

# Modell-Konfiguration
MODEL_CONFIG = {
    'price_model': {
        'input_size': 8,
        'hidden_size': 128,
        'num_layers': 2,
        'dropout': 0.2
    },
    'restock_model': {
        'input_size': 10,
        'hidden_size': 64,
        'dropout': 0.3
    }
}

# Modell-Pfade
MODEL_PATHS = {
    'price_model': 'models/price_prediction.pt',
    'restock_model': 'models/restock_prediction.pt'
}

def initialize_ml_components(cache_manager=None):
    """Initialisiert alle ML-Komponenten."""
    try:
        # Device-Konfiguration
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Modelle initialisieren
        price_model = PricePredictionModel(**MODEL_CONFIG['price_model']).to(device)
        restock_model = RestockPredictor(**MODEL_CONFIG['restock_model']).to(device)
        
        # Dataset Preparator
        dataset_preparator = DatasetPreparator(cache_manager=cache_manager)
        
        # Trainer
        trainer = ModelTrainer(
            price_model=price_model,
            restock_model=restock_model,
            device=device,
            cache_manager=cache_manager
        )
        
        # Lade existierende Modelle wenn vorhanden
        _load_existing_models(price_model, restock_model)
        
        return {
            'price_model': price_model,
            'restock_model': restock_model,
            'dataset_preparator': dataset_preparator,
            'trainer': trainer,
            'device': device
        }
    except Exception as e:
        logger.error(f"ML-Komponenten Initialisierungsfehler: {e}")
        raise

def _load_existing_models(price_model, restock_model):
    """Lädt existierende Modelle wenn vorhanden."""
    try:
        for model_name, path in MODEL_PATHS.items():
            model_path = Path(path)
            if model_path.exists():
                if model_name == 'price_model':
                    price_model.load_model(str(model_path))
                    logger.info("Preismodell geladen")
                elif model_name == 'restock_model':
                    restock_model.load_model(str(model_path))
                    logger.info("Restockmodell geladen")
    except Exception as e:
        logger.error(f"Fehler beim Laden existierender Modelle: {e}")

__all__ = [
    'PricePredictionModel',
    'RestockPredictor',
    'DatasetPreparator',
    'ModelTrainer',
    'initialize_ml_components'
]
