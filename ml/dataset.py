from typing import Tuple, List, Dict, Optional
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging
from pathlib import Path
import asyncio

class DatasetPreparator:
    def __init__(self, cache_manager=None):
        self.scaler = StandardScaler()
        self.logger = logging.getLogger("DatasetPreparator")
        self.cache_manager = cache_manager
        self.feature_columns = [
            'price', 'sales', 'restock_frequency', 
            'profit_margin', 'demand_score', 'brand_score',
            'seasonal_factor', 'market_volume'
        ]

    async def create_dataset(self, force_refresh: bool = False) -> Tuple[np.ndarray, np.ndarray]:
        """Erstellt einen Datensatz für das Training."""
        try:
            if not force_refresh and self.cache_manager:
                cached_data = await self.cache_manager.get('training_dataset')
                if cached_data:
                    return cached_data['features'], cached_data['targets']

            csv_path = Path("data/training_data.csv")
            if not csv_path.exists():
                self.logger.warning("Kein Trainingsdatensatz gefunden")
                return np.array([]), np.array([])

            df = await self.load_data(str(csv_path))
            if df.empty:
                return np.array([]), np.array([])

            features, targets = await self.prepare_features(df)
            if len(features) == 0:
                self.logger.warning("Keine Features erstellt")
                return np.array([]), np.array([])

            features_scaled = self.scaler.fit_transform(features)

            if self.cache_manager:
                await self.cache_manager.set('training_dataset', {
                    'features': features_scaled,
                    'targets': targets
                }, ttl=3600)

            return features_scaled, targets

        except Exception as e:
            self.logger.error(f"Fehler bei Dataset-Erstellung: {e}")
            return np.array([]), np.array([])

    async def load_data(self, csv_path: str) -> pd.DataFrame:
        """Lädt und validiert Datensatz asynchron."""
        try:
            df = pd.read_csv(csv_path)
            required_columns = ['sku', 'price', 'sales', 'timestamp'] + self.feature_columns
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.warning(f"Fehlende Spalten: {missing_columns}")
                for col in missing_columns:
                    df[col] = 0.0

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df

        except Exception as e:
            self.logger.error(f"Fehler beim Laden des Datasets: {e}")
            return pd.DataFrame()

    async def prepare_features(self, df: pd.DataFrame, lookback: int = 30) -> Tuple[np.ndarray, np.ndarray]:
        """Erstellt erweiterte Features für ML-Training."""
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
                    
                    feature_vector = await self._extract_features(window)
                    features.append(feature_vector)
                    targets.append(target)

            return np.array(features), np.array(targets)

        except Exception as e:
            self.logger.error(f"Fehler bei Feature-Erstellung: {e}")
            return np.array([]), np.array([])

    async def _extract_features(self, window: pd.DataFrame) -> List[float]:
        """Extrahiert erweiterte Features aus Zeitfenster."""
        try:
            return [
                window['price'].mean(),
                window['price'].std(),
                window['sales'].sum(),
                window['price'].max(),
                window['price'].min(),
                window['price'].iloc[-1],
                window['sales'].mean(),
                self._calculate_trend(window['price']),
                window['profit_margin'].mean(),
                window['demand_score'].mean(),
                window['brand_score'].mean(),
                window['seasonal_factor'].mean(),
                window['market_volume'].mean(),
                window['restock_frequency'].mean()
            ]
        except Exception as e:
            self.logger.error(f"Fehler bei Feature-Extraktion: {e}")
            return [0.0] * 14

    def _calculate_trend(self, prices: pd.Series) -> float:
        """Berechnet erweiterten Preistrend."""
        try:
            x = np.arange(len(prices))
            slope, _ = np.polyfit(x, prices, 1)
            return slope
        except Exception:
            return 0.0
