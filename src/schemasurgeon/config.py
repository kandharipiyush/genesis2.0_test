"""Configuration settings for SchemaSurgeon."""

import os
from pathlib import Path
from pydantic import BaseModel

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
AUDIT_DIR = DATA_DIR / "audit"
CONTRACTS_DIR = DATA_DIR / "contracts"

AUDIT_DIR.mkdir(parents=True, exist_ok=True)
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    """Runtime configuration settings."""

    mock_api_url: str = os.getenv("MOCK_API_URL", "http://127.0.0.1:8001")
    gateway_url: str = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")
    recovery_deadline_seconds: float = float(os.getenv("RECOVERY_DEADLINE_SECONDS", "4.0"))
    audit_persistence_timeout_ms: float = float(os.getenv("AUDIT_PERSISTENCE_TIMEOUT_MS", "250.0"))
    anti_flap_window_seconds: float = float(os.getenv("ANTI_FLAP_WINDOW_SECONDS", "30.0"))
    max_reheals_per_window: int = int(os.getenv("MAX_REHEALS_PER_WINDOW", "1"))
    min_confidence_score: float = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.50"))
    unique_match_margin: float = float(os.getenv("UNIQUE_MATCH_MARGIN", "0.15"))
    audit_log_path: Path = AUDIT_DIR / "audit_events.jsonl"
    trusted_origins: list[str] = [
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


settings = Settings()
