"""
🧠 KRONOS QUANTITATIVE ENGINE PACKAGE
=====================================
Production-grade quantitative trading framework powered by the Kronos
Financial Time-Series Foundation Model (AAAI 2026) and Conformal Risk Calibration.
"""

from kronos_engine.data_pipeline import DataPipeline, KronosTokenizer, MarketWindow
from kronos_engine.kronos_brain import KronosBrain, KronosSignalVector
from kronos_engine.calibration_audit import CalibrationAuditEngine, AuditResult
from kronos_engine.risk_manager import RiskSupervisor, RiskApproval
from kronos_engine.main_execution import KronosExecutionEngine

__all__ = [
    "DataPipeline",
    "KronosTokenizer",
    "MarketWindow",
    "KronosBrain",
    "KronosSignalVector",
    "CalibrationAuditEngine",
    "AuditResult",
    "RiskSupervisor",
    "RiskApproval",
    "KronosExecutionEngine",
]
