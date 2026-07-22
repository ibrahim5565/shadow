"""
AEGIS AI BRAIN TRAINER — Self-Learning Model
Trains on 159k+ historical decisions to predict BUY/SELL/WAIT
Uses real column names from brain_log.csv
"""
import os, sys
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from brain.gpt_core import AegisGPT

CSV_PATH   = os.path.join(BASE_DIR, "data", "brain_log.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_gpt.pt")
RESULT_PATH= os.path.join(BASE_DIR, "data", "training_result.txt")
MODELS_DIR = os.path.join(BASE_DIR, "models")

BATCH_SIZE    = 128
EPOCHS        = 100  # Increased for deeper learning
SEQ_LEN       = 16
LEARNING_RATE = 0.0005  # Reduced for stability

FEATURES = ['regime_score', 'structure_score', 'entry_score',
            'total_score', 'sl_points', 'tp_points', 'lot']


class TradingDataset(Dataset):
    def __init__(self, features, targets, seq_len=16):
        self.features = features.astype(np.float32)
        self.targets = targets.astype(np.int64)
        self.seq_len = seq_len

    def __len__(self):
        return len(self.features) - self.seq_len

    def __getitem__(self, idx):
        x = self.features[idx : idx + self.seq_len]
        y = self.targets[idx + self.seq_len]
        return torch.from_numpy(x), torch.tensor(y)


def train():
    print("=" * 55)
    print("   AEGIS AI BRAIN — SELF-LEARNING TRAINER")
    print("=" * 55)

    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found. Run bot first to collect data.")
        return False

    os.makedirs(MODELS_DIR, exist_ok=True)

    print(f"Loading data from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, encoding='latin1', low_memory=False, on_bad_lines='skip')
    print(f"Raw rows: {len(df)}")

    # Fill missing numeric columns
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    df[FEATURES] = df[FEATURES].fillna(0.0)

    # Normalize features to 0-1
    for col in FEATURES:
        max_val = df[col].max()
        if max_val > 0:
            df[col] = df[col] / max_val

    features = df[FEATURES].values.astype(np.float32)

    # Target: 0=WAIT, 1=BUY, 2=SELL
    direction_col = df.get('direction', pd.Series(['NA'] * len(df)))
    action_col    = df.get('action', pd.Series(['WAIT'] * len(df)))
    targets = []
    for a, d in zip(action_col, direction_col):
        if str(a) == 'WAIT' or str(d) == 'NA' or pd.isna(d):
            targets.append(0)
        elif str(d) == 'BUY':
            targets.append(1)
        elif str(d) == 'SELL':
            targets.append(2)
        else:
            targets.append(0)
    targets = np.array(targets, dtype=np.int64)

    # Temporal split: 85% train, 15% validation
    split_idx = int(len(features) * 0.85)
    
    train_features = features[:split_idx]
    train_targets = targets[:split_idx]
    
    val_features = features[split_idx:]
    val_targets = targets[split_idx:]

    train_dataset = TradingDataset(train_features, train_targets, seq_len=SEQ_LEN)
    val_dataset = TradingDataset(val_features, val_targets, seq_len=SEQ_LEN)

    if len(train_dataset) < BATCH_SIZE:
        print(f"ERROR: Not enough train data ({len(train_dataset)} rows). Need at least {BATCH_SIZE}.")
        return False

    train_dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_dataloader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # Initialize model with deeper architecture for better learning
    model = AegisGPT(n_layer=6, n_head=8, n_embd=256, seq_len=SEQ_LEN, input_dim=len(FEATURES))
    model.to(device)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")

    # Load existing model to continue training
    if os.path.exists(MODEL_PATH):
        try:
            model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
            print("Loaded existing model — continuing training...")
        except Exception as e:
            print(f"Starting fresh training... (Error loading model: {e})")

    # Stats
    train_buy  = (train_targets == 1).sum()
    train_sell = (train_targets == 2).sum()
    train_wait = (train_targets == 0).sum()
    
    val_buy  = (val_targets == 1).sum()
    val_sell = (val_targets == 2).sum()
    val_wait = (val_targets == 0).sum()
    
    print(f"Train Dataset: {len(train_dataset)} samples | WAIT:{train_wait} BUY:{train_buy} SELL:{train_sell}")
    print(f"Val Dataset: {len(val_dataset)} samples | WAIT:{val_wait} BUY:{val_buy} SELL:{val_sell}")

    # Compute class weights
    class_counts = [train_wait, train_buy, train_sell]
    total_samples = sum(class_counts)
    class_weights = [total_samples / (3.0 * count) if count > 0 else 1.0 for count in class_counts]
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)
    print(f"Class weights: {class_weights}")

    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor)
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_val_acc = 0.0
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0
        correct    = 0
        total      = 0

        for batch_idx, (data, target) in enumerate(train_dataloader):
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss   = criterion(output, target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()
            _, predicted = output.max(1)
            total   += target.size(0)
            correct += predicted.eq(target).sum().item()

            if batch_idx % 200 == 0:
                pct = 100 * batch_idx / len(train_dataloader)
                print(f"  Epoch {epoch+1:02d}/{EPOCHS} [{pct:5.1f}%] loss={loss.item():.4f}", end='\r')

        scheduler.step()
        train_acc = 100.0 * correct / total
        avg_train_loss = total_loss / len(train_dataloader)

        # Evaluate on validation set
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for data, target in val_dataloader:
                data, target = data.to(device), target.to(device)
                output = model(data)
                loss = criterion(output, target)
                val_loss += loss.item()
                _, predicted = output.max(1)
                val_total += target.size(0)
                val_correct += predicted.eq(target).sum().item()

        val_acc = 100.0 * val_correct / val_total
        avg_val_loss = val_loss / len(val_dataloader)

        print(f"Epoch {epoch+1:02d}/{EPOCHS} | Train Loss: {avg_train_loss:.4f} | Train Acc: {train_acc:.1f}% | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:.1f}%")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"  [SAVED] New best model saved ({val_acc:.1f}%)")

    # Save final model
    torch.save(model.state_dict(), MODEL_PATH)

    # Checkpoint and verify rollback stability
    try:
        from brain.model_version_manager import ModelVersionManager
        mvm = ModelVersionManager()
        mvm.save_checkpoint(
            MODEL_PATH, "aegis_gpt", val_loss=avg_val_loss, val_acc=val_acc,
            training_loss=avg_train_loss, training_metrics={"acc": train_acc},
            validation_metrics={"acc": val_acc},
            config_metadata={"epochs": EPOCHS, "batch_size": BATCH_SIZE, "seq_len": SEQ_LEN}
        )
        rolled_back = mvm.verify_and_rollback(MODEL_PATH, "aegis_gpt", avg_val_loss, val_acc)
        if rolled_back:
            print("  [ROLLBACK] Performance degraded. Rolled back to best stable model checkpoint.")
    except Exception as e:
        print(f"Error handling model checkpoints: {e}")

    summary = (
        f"Training Date  : {pd.Timestamp.now()}\n"
        f"Total Samples  : {len(train_dataset) + len(val_dataset)}\n"
        f"Train Samples  : {len(train_dataset)}\n"
        f"Val Samples    : {len(val_dataset)}\n"
        f"Epochs         : {EPOCHS}\n"
        f"Final Val Loss : {avg_val_loss:.4f}\n"
        f"Best Val Acc   : {best_val_acc:.1f}%\n"
        f"Final Val Acc  : {val_acc:.1f}%\n"
        f"Device         : {device}\n"
        f"Model Path     : {MODEL_PATH}\n"
    )
    with open(RESULT_PATH, "w") as f:
        f.write(summary)

    print("\n" + "=" * 55)
    print(summary)
    print("=" * 55)
    print(f"Model saved to: {MODEL_PATH}")
    return True


if __name__ == "__main__":
    success = train()
    sys.exit(0 if success else 1)
