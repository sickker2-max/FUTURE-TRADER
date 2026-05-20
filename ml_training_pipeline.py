# ============================================================================
# ML Training Pipeline with MLflow Integration
# Phase 2: Strategy & Intelligence - Week 16-17
# Integrates with existing feature engineering and model registry
# ============================================================================

import os
import time
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

import mlflow
import mlflow.pytorch
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit

from lstm_attention_model import LSTMAttentionModel, ModelConfig, PricePredictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration"""
    model_name: str = "lstm_attention_v1"
    experiment_name: str = "price_prediction"
    
    # Data parameters
    sequence_length: int = 60
    train_split: float = 0.7
    val_split: float = 0.15
    # test_split: 0.15 (implicit)
    
    # Training parameters
    batch_size: int = 32
    num_epochs: int = 100
    learning_rate: float = 0.001
    weight_decay: float = 1e-5
    early_stopping_patience: int = 10
    
    # Model parameters
    hidden_dim: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    attention_heads: int = 4
    
    # MLflow tracking
    mlflow_tracking_uri: str = "http://localhost:5000"
    artifact_location: str = "./mlruns"
    
    # Checkpointing
    checkpoint_dir: str = "./checkpoints"
    save_every_n_epochs: int = 10


class TimeSeriesDataset(Dataset):
    """Dataset for time series sequences"""
    
    def __init__(
        self,
        features: np.ndarray,
        targets: np.ndarray,
        sequence_length: int
    ):
        self.features = features
        self.targets = targets
        self.sequence_length = sequence_length
        
    def __len__(self) -> int:
        return len(self.features) - self.sequence_length
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.features[idx:idx + self.sequence_length]
        y = self.targets[idx + self.sequence_length]
        
        return torch.FloatTensor(x), torch.FloatTensor([y])


class MLTrainingPipeline:
    """Complete ML training pipeline with MLflow tracking"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Setup MLflow
        mlflow.set_tracking_uri(config.mlflow_tracking_uri)
        mlflow.set_experiment(config.experiment_name)
        
        # Create checkpoint directory
        os.makedirs(config.checkpoint_dir, exist_ok=True)
        
        # Initialize scalers
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        
        logger.info(f"Training pipeline initialized on device: {self.device}")
        
    def prepare_data(
        self,
        features: pd.DataFrame,
        target_column: str = 'close'
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """Prepare data for training"""
        logger.info("Preparing dataset...")
        
        # Extract target
        target = features[target_column].values
        feature_cols = [col for col in features.columns if col != target_column]
        feature_data = features[feature_cols].values
        
        # Calculate split indices
        n_samples = len(feature_data)
        train_size = int(n_samples * self.config.train_split)
        val_size = int(n_samples * self.config.val_split)
        
        # Split data (time series - no shuffle)
        train_features = feature_data[:train_size]
        train_targets = target[:train_size]
        
        val_features = feature_data[train_size:train_size + val_size]
        val_targets = target[train_size:train_size + val_size]
        
        test_features = feature_data[train_size + val_size:]
        test_targets = target[train_size + val_size:]
        
        # Fit scalers on training data only
        train_features_scaled = self.feature_scaler.fit_transform(train_features)
        train_targets_scaled = self.target_scaler.fit_transform(train_targets.reshape(-1, 1)).flatten()
        
        # Transform validation and test data
        val_features_scaled = self.feature_scaler.transform(val_features)
        val_targets_scaled = self.target_scaler.transform(val_targets.reshape(-1, 1)).flatten()
        
        test_features_scaled = self.feature_scaler.transform(test_features)
        test_targets_scaled = self.target_scaler.transform(test_targets.reshape(-1, 1)).flatten()
        
        # Create datasets
        train_dataset = TimeSeriesDataset(
            train_features_scaled, 
            train_targets_scaled,
            self.config.sequence_length
        )
        val_dataset = TimeSeriesDataset(
            val_features_scaled,
            val_targets_scaled,
            self.config.sequence_length
        )
        test_dataset = TimeSeriesDataset(
            test_features_scaled,
            test_targets_scaled,
            self.config.sequence_length
        )
        
        # Create dataloaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,  # Don't shuffle time series
            num_workers=4,
            pin_memory=True
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=4,
            pin_memory=True
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=4,
            pin_memory=True
        )
        
        logger.info(f"Dataset prepared: Train={len(train_dataset)}, Val={len(val_dataset)}, Test={len(test_dataset)}")
        
        return train_loader, val_loader, test_loader
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader, test_loader: DataLoader) -> Dict:
        """Train the model with MLflow tracking"""
        # Start MLflow run
        with mlflow.start_run(run_name=f"{self.config.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Log configuration
            mlflow.log_params(asdict(self.config))
            mlflow.log_param("device", str(self.device))
            
            # Initialize model
            model_config = ModelConfig(
                input_dim=train_loader.dataset.features.shape[1],
                hidden_dim=self.config.hidden_dim,
                num_layers=self.config.num_layers,
                dropout=self.config.dropout,
                attention_heads=self.config.attention_heads,
                sequence_length=self.config.sequence_length,
                output_dim=1
            )
            
            predictor = PricePredictor(model_config, device=str(self.device))
            predictor.setup_training(
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay
            )
            
            # Training loop
            best_val_loss = float('inf')
            patience_counter = 0
            training_history = {
                'train_loss': [],
                'val_loss': [],
                'val_mae': [],
                'learning_rate': []
            }
            
            logger.info("Starting training...")
            start_time = time.time()
            
            for epoch in range(self.config.num_epochs):
                epoch_start = time.time()
                
                # Training phase
                predictor.model.train()
                train_losses = []
                
                for batch_idx, (batch_x, batch_y) in enumerate(train_loader):
                    loss = predictor.train_step(batch_x, batch_y)
                    train_losses.append(loss)
                    
                    if batch_idx % 100 == 0:
                        logger.info(f"Epoch {epoch+1}/{self.config.num_epochs} - Batch {batch_idx}/{len(train_loader)} - Loss: {loss:.6f}")
                
                avg_train_loss = np.mean(train_losses)
                
                # Validation phase
                val_losses = []
                val_maes = []
                
                for batch_x, batch_y in val_loader:
                    val_loss, val_mae = predictor.validate(batch_x, batch_y)
                    val_losses.append(val_loss)
                    val_maes.append(val_mae)
                
                avg_val_loss = np.mean(val_losses)
                avg_val_mae = np.mean(val_maes)
                
                # Learning rate scheduling
                predictor.scheduler.step(avg_val_loss)
                current_lr = predictor.optimizer.param_groups[0]['lr']
                
                # Update history
                training_history['train_loss'].append(avg_train_loss)
                training_history['val_loss'].append(avg_val_loss)
                training_history['val_mae'].append(avg_val_mae)
                training_history['learning_rate'].append(current_lr)
                
                # Log metrics to MLflow
                mlflow.log_metrics({
                    'train_loss': avg_train_loss,
                    'val_loss': avg_val_loss,
                    'val_mae': avg_val_mae,
                    'learning_rate': current_lr
                }, step=epoch)
                
                epoch_time = time.time() - epoch_start
                logger.info(
                    f"Epoch {epoch+1}/{self.config.num_epochs} - "
                    f"Train Loss: {avg_train_loss:.6f} - "
                    f"Val Loss: {avg_val_loss:.6f} - "
                    f"Val MAE: {avg_val_mae:.6f} - "
                    f"LR: {current_lr:.6f} - "
                    f"Time: {epoch_time:.2f}s"
                )
                
                # Save checkpoint
                if (epoch + 1) % self.config.save_every_n_epochs == 0:
                    checkpoint_path = os.path.join(
                        self.config.checkpoint_dir,
                        f"{self.config.model_name}_epoch_{epoch+1}.pt"
                    )
                    predictor.save_checkpoint(checkpoint_path)
                    mlflow.log_artifact(checkpoint_path)
                
                # Early stopping
                if avg_val_loss < best_val_loss:
                    best_val_loss = avg_val_loss
                    patience_counter = 0
                    
                    # Save best model
                    best_model_path = os.path.join(
                        self.config.checkpoint_dir,
                        f"{self.config.model_name}_best.pt"
                    )
                    predictor.save_checkpoint(best_model_path)
                    mlflow.log_artifact(best_model_path)
                    
                    logger.info(f"New best model saved with val_loss: {best_val_loss:.6f}")
                else:
                    patience_counter += 1
                    
                if patience_counter >= self.config.early_stopping_patience:
                    logger.info(f"Early stopping triggered after {epoch+1} epochs")
                    break
            
            total_time = time.time() - start_time
            logger.info(f"Training completed in {total_time:.2f}s")
            
            # Load best model for testing
            predictor.load_checkpoint(best_model_path)
            
            # Test evaluation
            test_losses = []
            test_maes = []
            all_predictions = []
            all_targets = []
            
            for batch_x, batch_y in test_loader:
                test_loss, test_mae = predictor.validate(batch_x, batch_y)
                test_losses.append(test_loss)
                test_maes.append(test_mae)
                
                # Get predictions for analysis
                result = predictor.predict(batch_x)
                all_predictions.extend(result['prediction'].flatten())
                all_targets.extend(batch_y.numpy().flatten())
            
            avg_test_loss = np.mean(test_losses)
            avg_test_mae = np.mean(test_maes)
            
            # Calculate additional metrics
            predictions = np.array(all_predictions)
            targets = np.array(all_targets)
            
            # Inverse transform for real-world metrics
            predictions_real = self.target_scaler.inverse_transform(predictions.reshape(-1, 1)).flatten()
            targets_real = self.target_scaler.inverse_transform(targets.reshape(-1, 1)).flatten()
            
            mape = np.mean(np.abs((targets_real - predictions_real) / targets_real)) * 100
            rmse = np.sqrt(np.mean((targets_real - predictions_real) ** 2))
            
            # Directional accuracy
            direction_correct = np.mean(
                np.sign(predictions_real[1:] - predictions_real[:-1]) == 
                np.sign(targets_real[1:] - targets_real[:-1])
            ) * 100
            
            # Log final metrics
            final_metrics = {
                'test_loss': avg_test_loss,
                'test_mae': avg_test_mae,
                'test_mape': mape,
                'test_rmse': rmse,
                'directional_accuracy': direction_correct,
                'training_time_seconds': total_time,
                'best_epoch': epoch + 1 - patience_counter
            }
            
            mlflow.log_metrics(final_metrics)
            
            # Log model to MLflow
            mlflow.pytorch.log_model(
                predictor.model,
                "model",
                registered_model_name=self.config.model_name
            )
            
            logger.info(f"Test Results - Loss: {avg_test_loss:.6f}, MAE: {avg_test_mae:.6f}, "
                       f"MAPE: {mape:.2f}%, RMSE: {rmse:.2f}, Dir Acc: {direction_correct:.2f}%")
            
            return {
                'predictor': predictor,
                'history': training_history,
                'metrics': final_metrics,
                'test_predictions': predictions_real,
                'test_targets': targets_real
            }


def generate_sample_features(n_samples: int = 10000, n_features: int = 50) -> pd.DataFrame:
    """Generate sample feature data for demonstration"""
    np.random.seed(42)
    
    # Generate synthetic price data with trend and seasonality
    t = np.arange(n_samples)
    trend = 0.01 * t
    seasonality = 10 * np.sin(2 * np.pi * t / 100)
    noise = np.random.randn(n_samples) * 2
    close = 100 + trend + seasonality + noise
    
    # Generate random features
    features = {
        'close': close,
        **{f'feature_{i}': np.random.randn(n_samples) for i in range(n_features - 1)}
    }
    
    return pd.DataFrame(features)


if __name__ == "__main__":
    # Configuration
    config = TrainingConfig(
        model_name="lstm_attention_btc_v1",
        experiment_name="btc_price_prediction",
        num_epochs=50,
        batch_size=64,
        learning_rate=0.001,
        early_stopping_patience=10
    )
    
    # Initialize pipeline
    pipeline = MLTrainingPipeline(config)
    
    # Generate or load data
    features_df = generate_sample_features(n_samples=10000, n_features=50)
    
    # Prepare data
    train_loader, val_loader, test_loader = pipeline.prepare_data(
        features_df,
        target_column='close'
    )
    
    # Train model
    results = pipeline.train(train_loader, val_loader, test_loader)
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Final Test Loss: {results['metrics']['test_loss']:.6f}")
    print(f"Final Test MAE: {results['metrics']['test_mae']:.6f}")
    print(f"MAPE: {results['metrics']['test_mape']:.2f}%")
    print(f"RMSE: {results['metrics']['test_rmse']:.2f}")
    print(f"Directional Accuracy: {results['metrics']['directional_accuracy']:.2f}%")
    print(f"Training Time: {results['metrics']['training_time_seconds']:.2f}s")
    print("="*60)
