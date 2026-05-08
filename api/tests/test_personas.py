"""Tests for persona normalization and KPI highlight mapping."""

import pytest
from routers.insights import ALLOWED_PERSONAS as INSIGHT_PERSONAS
from routers.insights import PERSONA_FRAMING
from routers.kpi import (
    ALLOWED_PERSONAS,
    PERSONA_HIGHLIGHT_KPIS,
    _normalize_persona,
)


@pytest.mark.parametrize("value", list(ALLOWED_PERSONAS))
def test_known_personas_pass_through(value: str):
    assert _normalize_persona(value) == value


@pytest.mark.parametrize("value", ["", None, "admin", "marketing", "OPS", "ops "])
def test_unknown_personas_default_to_ops(value):
    assert _normalize_persona(value) == "ops"


def test_kpi_highlights_cover_every_persona():
    for p in ALLOWED_PERSONAS:
        assert p in PERSONA_HIGHLIGHT_KPIS
        assert len(PERSONA_HIGHLIGHT_KPIS[p]) >= 1


def test_persona_definitions_aligned_between_kpi_and_insights():
    """ops/finance/supply must exist in both modules — drift would silently break the dashboard."""
    assert set(ALLOWED_PERSONAS) == set(INSIGHT_PERSONAS)
    for p in ALLOWED_PERSONAS:
        assert p in PERSONA_FRAMING
        assert "role" in PERSONA_FRAMING[p]
        assert "focus" in PERSONA_FRAMING[p]
        assert "tone" in PERSONA_FRAMING[p]
