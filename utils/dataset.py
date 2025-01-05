import pandas as pd
import numpy as np
from typing import Tuple, List, Dict
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging
from datetime import datetime
from pathlib import Path

class DatasetPreparator:
    def __init__(self):
        self.scaler = StandardScaler()
        self.logger = logging.getLogger("DatasetPreparator")

    async def create_dataset(self) -> Tuple[np.ndarray, np.ndarray]:
        """Erstellt einen Datensatz für das Training."""
        try:
            csv_path = Path("data/training_data.csv")
            if not csv_path.exists():
                self.logger.warning("Kein Trainingsdatensatz gefunden")
                return np.array([]), np.array([])

            df = self.load_data(str(csv_path))
            features, targets = self.prepare_features(df, lookback=7)  # Reduzierter lookback
            
            if len(features) == 0:
                self.logger.warning("Keine Features erstellt")
                return np.array([]), np.array([])

            features_scaled = self.scaler.fit_transform(features)
            return features_scaled, targets

        except Exception as e:
            self.logger.error(f"Fehler bei Dataset-Erstellung: {e}")
            return np.array([]), np.array([])

    def load_data(self, csv_path: str) -> pd.DataFrame:
        """Lädt und validiert Datensatz."""
        try:
            df = pd.read_csv(csv_path)
            required_columns = ['sku', 'price', 'sales', 'timestamp']
            if not all(col in df.columns for col in required_columns):
                raise ValueError("Missing required columns in dataset")
            return df
        except Exception as e:
            self.logger.error(f"Error loading dataset: {e}")
            raise

    def prepare_features(
        self,
        df: pd.DataFrame,
        lookback: int = 7  # Reduzierter lookback-Parameter
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Erstellt Features für ML-Training."""
        try:
            features = []
            targets = []
            for sku in df['sku'].unique():
                sku_data = df[df['sku'] == sku].sort_values('timestamp')
                if len(sku_data) < lookback + 1:
                    continue
                
                for i in range(len(sku_data) - lookback):
                    window = sku_data.iloc[i:i+lookback]
                    target = sku_data.iloc[i+lookback]['price']
                    feature_vector = self._extract_features(window)
                    features.append(feature_vector)
                    targets.append(target)
                    
            return np.array(features), np.array(targets)
        except Exception as e:
            self.logger.error(f"Error preparing features: {e}")
            raise

    def _extract_features(self, window: pd.DataFrame) -> List[float]:
        """Extrahiert Features aus Zeitfenster."""
        return [
            window['price'].mean(),
            window['price'].std(),
            window['sales'].sum(),
            window['price'].max(),
            window['price'].min(),
            window['price'].iloc[-1],  # Letzter Preis
            window['sales'].mean(),
            self._calculate_trend(window['price'])
        ]

    def _calculate_trend(self, prices: pd.Series) -> float:
        """Berechnet Preistrend."""
        try:
            x = np.arange(len(prices))
            slope, _ = np.polyfit(x, prices, 1)
            return slope
        except Exception:
            return 0.0

    def create_train_test_split(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        test_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Erstellt Train-Test-Split mit Skalierung."""
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=test_size, random_state=42
            )
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            return X_train_scaled, X_test_scaled, y_train, y_test
        except Exception as e:
            self.logger.error(f"Error creating train-test split: {e}")
            raise
