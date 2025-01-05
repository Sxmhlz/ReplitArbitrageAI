from typing import Optional, Tuple, Dict
import torch
import torch.nn as nn
import torch.optim as optim
import logging
from pathlib import Path
import asyncio
import numpy as np
from .model import PricePredictionModel, RestockPredictor

class ModelTrainer:
    def __init__(
        self,
        price_model: PricePredictionModel,
        restock_model: Optional[RestockPredictor] = None,
        device: torch.device = None,
        cache_manager = None
    ):
        self.logger = logging.getLogger("ModelTrainer")
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.cache_manager = cache_manager

        # Modelle
        self.price_model = price_model.to(self.device)
        self.restock_model = restock_model.to(self.device) if restock_model else None

        # Optimierer mit verbesserten Parametern
        self.price_optimizer = optim.Adam(
            self.price_model.parameters(),
            lr=0.001,
            betas=(0.9, 0.999),
            weight_decay=0.0001
        )
        
        if self.restock_model:
            self.restock_optimizer = optim.Adam(
                self.restock_model.parameters(),
                lr=0.001,
                betas=(0.9, 0.999),
                weight_decay=0.0001
            )

        # Loss Functions mit Gewichtung
        self.price_criterion = nn.MSELoss()
        self.restock_criterion = nn.BCELoss()

        # Erweiterte Statistiken
        self.training_stats = {
            'price_losses': [],
            'restock_losses': [],
            'evaluations': [],
            'learning_rates': [],
            'validation_metrics': [],
            'training_duration': [],
            'model_checkpoints': []
        }

    async def train_price_model(
        self,
        features: torch.Tensor,
        targets: torch.Tensor,
        batch_size: int = 32,
        epochs: int = 10,
        validation_split: float = 0.1
    ) -> float:
        try:
            self.price_model.train()
            features = features.to(self.device)
            targets = targets.to(self.device)

            # Validierungssplit
            val_size = int(len(features) * validation_split)
            train_features, val_features = features[:-val_size], features[-val_size:]
            train_targets, val_targets = targets[:-val_size], targets[-val_size:]

            dataset = torch.utils.data.TensorDataset(train_features, train_targets)
            dataloader = torch.utils.data.DataLoader(
                dataset,
                batch_size=batch_size,
                shuffle=True,
                num_workers=2,
                pin_memory=True
            )

            best_val_loss = float('inf')
            patience = 5
            patience_counter = 0

            for epoch in range(epochs):
                epoch_start_time = time.time()
                epoch_loss = 0.0
                
                for batch_features, batch_targets in dataloader:
                    self.price_optimizer.zero_grad()
                    predictions, _ = self.price_model(batch_features)
                    loss = self.price_criterion(predictions, batch_targets)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.price_model.parameters(), 1.0)
                    self.price_optimizer.step()
                    epoch_loss += loss.item()

                avg_loss = epoch_loss / len(dataloader)
                
                # Validierung
                val_loss = await self._validate_price_model(val_features, val_targets)
                
                self.training_stats['price_losses'].append(avg_loss)
                self.training_stats['validation_metrics'].append(val_loss)
                self.training_stats['training_duration'].append(time.time() - epoch_start_time)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    await self._save_checkpoint(epoch, avg_loss, val_loss)
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= patience:
                    self.logger.info("Early stopping triggered")
                    break

                await asyncio.sleep(0)

            return best_val_loss

        except Exception as e:
            self.logger.error(f"Fehler beim Training des Preismodells: {e}")
            raise

    async def _validate_price_model(self, features: torch.Tensor, targets: torch.Tensor) -> float:
        """Validiert das Preismodell."""
        self.price_model.eval()
        with torch.no_grad():
            predictions, _ = self.price_model(features)
            val_loss = self.price_criterion(predictions, targets).item()
        self.price_model.train()
        return val_loss

    async def _save_checkpoint(self, epoch: int, train_loss: float, val_loss: float) -> None:
        """Speichert Modell-Checkpoints."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.price_model.state_dict(),
            'optimizer_state_dict': self.price_optimizer.state_dict(),
            'train_loss': train_loss,
            'val_loss': val_loss
        }
        
        checkpoint_path = Path(f'models/checkpoint_epoch_{epoch}.pt')
        torch.save(checkpoint, checkpoint_path)
        self.training_stats['model_checkpoints'].append(str(checkpoint_path))

        if self.cache_manager:
            await self.cache_manager.set(
                f'model_checkpoint_{epoch}',
                {
                    'path': str(checkpoint_path),
                    'metrics': {
                        'train_loss': train_loss,
                        'val_loss': val_loss
                    }
                },
                ttl=86400
            )

    async def evaluate_models(self, test_features: torch.Tensor, test_targets: torch.Tensor) -> Dict:
        """Evaluiert beide Modelle."""
        try:
            results = {}
            
            # Preismodell-Evaluation
            if self.price_model:
                price_metrics = await self.evaluate_price_model(test_features, test_targets)
                results['price_model'] = price_metrics
            
            # Restock-Modell-Evaluation
            if self.restock_model:
                restock_metrics = await self.evaluate_restock_model(test_features, test_targets)
                results['restock_model'] = restock_metrics

            return results

        except Exception as e:
            self.logger.error(f"Evaluierungsfehler: {e}")
            return {}
