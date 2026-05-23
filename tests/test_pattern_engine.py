"""Testes do PatternEngine com dados sintéticos (numpy → DataFrame OHLCV)."""  # MELHORIA
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pattern_engine import PatternEngine, PatternSnapshot, score_pattern as _score_pattern_from_snapshot


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(closes: np.ndarray, noise: float = 0.005) -> pd.DataFrame:
    """Cria DataFrame OHLCV a partir de um array de fechamentos."""
    rng = np.random.default_rng(42)
    n = len(closes)
    highs = closes * (1 + np.abs(rng.normal(0, noise, n)))
    lows = closes * (1 - np.abs(rng.normal(0, noise, n)))
    opens = closes * (1 + rng.normal(0, noise / 2, n))
    volumes = rng.integers(100_000, 1_000_000, n).astype(float)
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes})


def _make_flat(n: int = 200, base: float = 100.0) -> np.ndarray:
    return np.full(n, base)


# ---------------------------------------------------------------------------
# Test 1 — double_bottom detectado
# ---------------------------------------------------------------------------

def test_double_bottom_detected():  # MELHORIA
    """Dois vales claros separados por ~30 barras, retração ≥5%."""
    closes = np.linspace(120, 100, 50).tolist()   # queda inicial
    closes += np.linspace(100, 110, 20).tolist()  # recuperação
    closes += np.linspace(110, 100.5, 30).tolist()  # segundo vale próximo do primeiro
    closes += np.linspace(100.5, 115, 20).tolist()  # recuperação final
    # pad para 150 barras mínimas
    pad = [115.0] * (200 - len(closes))
    closes = pad + closes
    df = _make_ohlcv(np.array(closes))

    engine = PatternEngine()
    snap = engine.analyze(df)

    double_bottom = next((p for p in snap.patterns_detected if p.pattern_name == "double_bottom"), None)
    assert double_bottom is not None, "PatternResult para double_bottom deve existir"
    assert double_bottom.detected is True, "double_bottom deve ser detectado nos dados sintéticos"


# ---------------------------------------------------------------------------
# Test 2 — head_shoulders_top seta has_bearish_warning
# ---------------------------------------------------------------------------

def test_head_shoulders_top_sets_bearish_warning():  # MELHORIA
    """Três picos com o central maior → has_bearish_warning=True."""
    # ombro esquerdo
    closes = list(np.linspace(100, 115, 20))  # subida
    closes += list(np.linspace(115, 108, 15))  # retração
    # cabeça (pico maior)
    closes += list(np.linspace(108, 125, 20))
    closes += list(np.linspace(125, 108, 20))
    # ombro direito
    closes += list(np.linspace(108, 114, 20))
    closes += list(np.linspace(114, 100, 15))
    pad = [100.0] * (200 - len(closes))
    closes = pad + closes

    df = _make_ohlcv(np.array(closes), noise=0.002)

    engine = PatternEngine()
    snap = engine.analyze(df)

    assert snap.has_bearish_warning is True, "H&S topo deve disparar has_bearish_warning=True"


# ---------------------------------------------------------------------------
# Test 3 — dados insuficientes retornam snapshot zerado
# ---------------------------------------------------------------------------

def test_insufficient_data_returns_empty_snapshot():  # MELHORIA
    """50 linhas → aggregate_pattern_score == 0."""
    closes = np.linspace(100, 90, 50)
    df = _make_ohlcv(closes)

    engine = PatternEngine()
    snap = engine.analyze(df)

    assert snap.aggregate_pattern_score == 0.0, "Com <120 barras o score deve ser 0.0"


# ---------------------------------------------------------------------------
# Test 4 — hammer candle detectado
# ---------------------------------------------------------------------------

def test_hammer_candle_detected():  # MELHORIA
    """Barra com corpo pequeno e sombra inferior longa → candle_pattern == 'hammer'."""
    closes = np.full(200, 100.0)
    df = _make_ohlcv(closes, noise=0.001)

    # Substitui a última barra por um hammer perfeito
    df.iloc[-1, df.columns.get_loc("Open")] = 100.0
    df.iloc[-1, df.columns.get_loc("Close")] = 100.5   # corpo pequeno para cima
    df.iloc[-1, df.columns.get_loc("High")] = 100.6    # sombra superior mínima
    df.iloc[-1, df.columns.get_loc("Low")] = 97.0      # sombra inferior longa (~3× corpo)

    engine = PatternEngine()
    snap = engine.analyze(df)

    assert snap.candle_pattern == "hammer", f"Esperado 'hammer', obtido '{snap.candle_pattern}'"
    assert snap.candle_direction == "bullish"


# ---------------------------------------------------------------------------
# Test 5 — score_pattern retorna 0 quando has_bearish_warning=True
# ---------------------------------------------------------------------------

def test_score_pattern_zero_on_bearish_warning():  # MELHORIA
    """Mock com has_bearish_warning=True → score_pattern() == 0."""
    from src.scoring_engine import score_pattern

    class _FakeTechnical:
        class _FakePS:
            has_bearish_warning = True
            aggregate_pattern_score = 9.0
            candle_direction = "bullish"
            candle_success_rate = 0.63
        pattern_snapshot = _FakePS()

    result = score_pattern(_FakeTechnical())
    assert result == 0, f"Esperado 0 (bearish warning), obtido {result}"
