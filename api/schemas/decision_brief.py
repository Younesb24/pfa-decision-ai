"""
Pydantic schema for the structured DecisionBrief produced by the tool-using agent.

Every field maps directly to a UI surface on the DecisionBriefCard (Day 8).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """One data point surfaced by an agent tool call."""

    metric: str = Field(description="Human-readable metric name, e.g. 'OTIF Rate'")
    value: str | float | int = Field(description="The observed value")
    source: str = Field(
        description="Gold table that provided this, e.g. 'gold.agg_daily_ops_kpi'"
    )
    as_of: str | None = Field(default=None, description="ISO date of the data point")
    unit: str | None = Field(default=None, description="Label: '%', 'BRL', 'days', etc.")


class ChartHint(BaseModel):
    """Optional chart spec rendered by the DynamicChart component."""

    chart_type: Literal["bar", "line", "area"] = "line"
    x_key: str
    y_key: str
    title: str | None = None
    data: list[dict] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    """A concrete next step the operator can click to fire."""

    label: str = Field(description="Button label, e.g. 'Draft seller warning email'")
    action_type: Literal["email", "webhook", "escalation", "review"] = "review"
    urgency: Literal["low", "medium", "high"] = "medium"
    payload: dict = Field(default_factory=dict)


class DecisionBrief(BaseModel):
    """
    Structured output of the Decision Analyst tool-use loop.

    The four narrative fields map to card sections in the dashboard.
    Evidence pills back each claim with a Gold-layer source citation.
    """

    question: str
    what_happened: str = Field(
        description="One-paragraph factual summary of what the data shows"
    )
    is_it_abnormal: str = Field(
        description="Whether the pattern is abnormal and the statistical context"
    )
    why_it_matters: str = Field(description="Business impact for the ops persona")
    evidence: list[Evidence] = Field(default_factory=list)
    chart_hint: ChartHint | None = None
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    tool_calls_made: list[str] = Field(default_factory=list)
    generated_at: str
    provider: str | None = None
    model: str | None = None
