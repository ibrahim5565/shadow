import os
import shutil
import json
import logging
from datetime import datetime

logger = logging.getLogger("aegis.model_version_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINT_DIR = os.path.join(BASE_DIR, "models", "checkpoints")
REGISTRY_FILE = os.path.join(CHECKPOINT_DIR, "model_registry.json")

class ModelVersionManager:
    def __init__(self):
        os.makedirs(CHECKPOINT_DIR, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> dict:
        if os.path.exists(REGISTRY_FILE):
            try:
                with open(REGISTRY_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading model registry: {e}")
        return {"checkpoints": [], "active_version": None}

    def _save_registry(self):
        try:
            with open(REGISTRY_FILE, "w") as f:
                json.dump(self.registry, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving model registry: {e}")

    def save_checkpoint(self, source_path: str, model_name: str, val_loss: float, val_acc: float,
                        training_loss: float = 0.0, training_metrics: dict = None,
                        validation_metrics: dict = None, config_metadata: dict = None,
                        status: str = "research", model_card: dict = None) -> str:
        """
        Saves a checkpoint of the model, registers it, and prunes old checkpoints.
        """
        if not os.path.exists(source_path):
            logger.error(f"Source model file not found for checkpointing: {source_path}")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_filename = f"{model_name}_{timestamp}_loss{val_loss:.4f}_acc{val_acc:.1f}.pt"
        dest_path = os.path.join(CHECKPOINT_DIR, checkpoint_filename)

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"[CKPT] Checkpoint saved: {checkpoint_filename}")

            version_num = f"8.0.{len(self.registry['checkpoints']) + 1}"

            # Register in metadata
            checkpoint_info = {
                "version": version_num,
                "filename": checkpoint_filename,
                "timestamp": datetime.now().isoformat(),
                "val_loss": val_loss,
                "val_acc": val_acc,
                "training_loss": training_loss,
                "training_metrics": training_metrics or {},
                "validation_metrics": validation_metrics or {},
                "config_metadata": config_metadata or {},
                "stable": True,
                # ── QUANT X Extensions ──────────────────────────────
                "status": status,  # research | shadow | challenger | champion | retired
                "model_card": model_card or {
                    "training_window": "unknown",
                    "intended_regime": "all",
                    "limitations": "none"
                }
            }
            self.registry["checkpoints"].append(checkpoint_info)
            self.registry["active_version"] = checkpoint_filename

            # Prune to last 5 checkpoints
            self._prune_checkpoints(model_name)
            self._save_registry()
            return dest_path
        except Exception as e:
            logger.error(f"Failed to copy model checkpoint: {e}")
            return ""

            return ""

    def _prune_checkpoints(self, model_name: str):
        # Keep only the last 5 checkpoints for this model name
        checkpoints = [c for c in self.registry["checkpoints"] if c["filename"].startswith(model_name)]
        if len(checkpoints) > 5:
            # Sort by timestamp (oldest first)
            checkpoints.sort(key=lambda x: x["timestamp"])
            to_remove = checkpoints[:-5]
            for c in to_remove:
                file_path = os.path.join(CHECKPOINT_DIR, c["filename"])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"[PRUNE] Pruned old checkpoint: {c['filename']}")
                    except Exception as e:
                        logger.error(f"Error removing pruned file: {e}")
                self.registry["checkpoints"].remove(c)

    def verify_and_rollback(self, dest_model_path: str, model_name: str, current_loss: float, current_acc: float) -> bool:
        """
        Verifies performance. If current performance is degraded compared to the best stable version,
        restores the best stable version to dest_model_path.
        """
        checkpoints = [c for c in self.registry["checkpoints"] if c["filename"].startswith(model_name) and c.get("stable", True)]
        if not checkpoints:
            logger.info("No prior stable checkpoints found for validation comparisons.")
            return False

        # Find best checkpoint (highest accuracy, lowest loss as tie-breaker)
        best_ckpt = max(checkpoints, key=lambda x: (x["val_acc"], -x["val_loss"]))
        
        logger.info(f"Comparing current performance (Acc: {current_acc:.1f}%, Loss: {current_loss:.4f}) with best checkpoint (Acc: {best_ckpt['val_acc']:.1f}%, Loss: {best_ckpt['val_loss']:.4f})")

        # Rollback conditions: Accuracy drops below 50% OR validation loss is 1.5x higher than best stable loss
        is_degraded = False
        reason = ""
        
        if current_acc < 50.0:
            is_degraded = True
            reason = f"Validation accuracy dropped below critical threshold (Current: {current_acc:.1f}% < 50%)"
        elif best_ckpt["val_loss"] > 0 and current_loss > best_ckpt["val_loss"] * 1.5:
            is_degraded = True
            reason = f"Validation loss increased significantly (Current: {current_loss:.4f} > 1.5x of Best: {best_ckpt['val_loss']:.4f})"

        if is_degraded:
            logger.warning(f"[WARN] MODEL DEGRADATION DETECTED: {reason}. Triggering automatic rollback...")
            try:
                from modules.telegram_bot import TelegramBot
                TelegramBot().send(f"[ROLLBACK] Model degradation: {reason}. Triggering rollback...")
            except Exception:
                pass
            best_ckpt_path = os.path.join(CHECKPOINT_DIR, best_ckpt["filename"])
            if os.path.exists(best_ckpt_path):
                try:
                    shutil.copy2(best_ckpt_path, dest_model_path)
                    logger.info(f"[ROLLBACK] Rollback SUCCESSFUL: Restored best stable model {best_ckpt['filename']} to {dest_model_path}")
                    try:
                        TelegramBot().send(f"[ROLLBACK] Rollback SUCCESSFUL: Restored best stable model {best_ckpt['filename']}")
                    except Exception:
                        pass
                    return True
                except Exception as e:
                    logger.error(f"Failed to copy rollback checkpoint: {e}")
            else:
                logger.error(f"Best checkpoint file {best_ckpt['filename']} not found on disk. Cannot rollback.")
        else:
            logger.info("[OK] Model validation checks passed. Performance is stable.")
            
        return False
