import torch
import torch.nn as nn
from typing import Optional, Tuple, Dict
import logging
from pathlib import Path
import numpy as np

class PricePredictionModel(nn.Module):
    def __init__(
        self,
        input_size: int = 8,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.2
    ):
        super().__init__()
        self.logger = logging.getLogger("PricePredictionModel")
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM Layer
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )
        
        # Fully Connected Layers mit erweiterten Features
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    async def predict(self, features: np.ndarray) -> float:
        """Asynchrone Vorhersage für Bot-Integration."""
        try:
            with torch.no_grad():
                x = torch.FloatTensor(features).unsqueeze(0).unsqueeze(0)
                predictions, _ = self.forward(x)
                return float(predictions.squeeze().item())
        except Exception as e:
            self.logger.error(f"Vorhersagefehler: {e}")
            return 0.0

    def forward(
        self,
        x: torch.Tensor,
        hidden: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]:
        try:
            lstm_out, hidden = self.lstm(x, hidden)
            last_hidden = lstm_out[:, -1, :]
            predictions = self.fc(last_hidden)
            return predictions, hidden
        except Exception as e:
            self.logger.error(f"Forward-Pass-Fehler: {e}")
            raise

class RestockPredictor(nn.Module):
    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        dropout: float = 0.3
    ):
        super().__init__()
        self.logger = logging.getLogger("RestockPredictor")
        
        # Erweiterte Feature Extraction
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Verbesserte Prediction Layers
        self.predictor = nn.Sequential(
            nn.Linear(hidden_size // 2, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    async def predict_restock(self, features: np.ndarray) -> float:
        """Asynchrone Restock-Vorhersage für Bot-Integration."""
        try:
            with torch.no_grad():
                x = torch.FloatTensor(features)
                prediction = self.forward(x)
                return float(prediction.squeeze().item())
        except Exception as e:
            self.logger.error(f"Restock-Vorhersagefehler: {e}")
            return 0.0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        try:
            features = self.feature_extractor(x)
            predictions = self.predictor(features)
            return predictions
        except Exception as e:
            self.logger.error(f"Forward-Pass-Fehler: {e}")
            raise

# Gemeinsame Modell-Management-Funktionen
def save_model(model: nn.Module, path: str) -> bool:
    try:
        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        state_dict = {
            'model_state_dict': model.state_dict(),
            'model_config': {
                'input_size': model.feature_extractor[0].in_features 
                if isinstance(model, RestockPredictor)
                else model.lstm.input_size,
                'hidden_size': model.hidden_size if hasattr(model, 'hidden_size') else None,
                'num_layers': model.num_layers if hasattr(model, 'num_layers') else None
            }
        }
        
        torch.save(state_dict, save_path)
        return True
    except Exception as e:
        logging.error(f"Fehler beim Speichern des Modells: {e}")
        return False

def load_model(model_class, path: str) -> Optional[nn.Module]:
    try:
        checkpoint = torch.load(path)
        config = checkpoint['model_config']
        
        if model_class == PricePredictionModel:
            model = model_class(
                input_size=config['input_size'],
                hidden_size=config['hidden_size'],
                num_layers=config['num_layers']
            )
        else:
            model = model_class(input_size=config['input_size'])
            
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        return model
    except Exception as e:
        logging.error(f"Fehler beim Laden des Modells: {e}")
        return None
