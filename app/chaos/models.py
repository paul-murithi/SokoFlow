from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    component: str
    passed: bool
    details: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None


class ScenarioResult(BaseModel):
    scenario_name: str
    description: str = ""
    passed: bool
    duration: float
    correlation_id: str
    steps: list[str] = Field(default_factory=list)
    validations: list[ValidationResult] = Field(default_factory=list)
    error_message: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChaosReport(BaseModel):
    title: str = "SokoFlow Chaos Testing Suite"
    environment: str = "local"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_scenarios: int = 0
    passed_count: int = 0
    failed_count: int = 0
    pass_rate: float = 0.0
    total_duration: float = 0.0
    coverage: float = 100.0
    results: list[ScenarioResult] = Field(default_factory=list)
