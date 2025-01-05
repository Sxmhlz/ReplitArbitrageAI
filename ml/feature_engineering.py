class FeatureExtractor:
    def extract_features(self, product_data: Dict) -> torch.Tensor:
        features = [
            self._calculate_price_momentum(product_data),
            self._calculate_sales_velocity(product_data),
            self._calculate_seasonality(product_data),
            self._calculate_restock_probability(product_data)
        ]
        return torch.tensor(features, dtype=torch.float32)