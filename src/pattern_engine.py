"""Detecção de padrões gráficos e de candle baseada nas estatísticas do Bulkowski."""  # MELHORIA
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.signal import argrelmin, argrelmax  # MELHORIA


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PatternResult:  # MELHORIA
    pattern_name: str        # snake_case
    detected: bool
    confidence: float        # 0.0–1.0
    breakout_direction: str  # "bullish" | "bearish" | "neutral"
    success_rate: float      # constante Bulkowski
    pattern_score: float     # 0–10, só conta se detected=True
    detail: str


@dataclass
class PatternSnapshot:  # MELHORIA
    patterns_detected: list[PatternResult] = field(default_factory=list)
    best_pattern: PatternResult | None = None
    aggregate_pattern_score: float = 0.0    # soma dos scores, teto 10.0
    has_bearish_warning: bool = False       # True se H&S top ou descending_triangle
    candle_pattern: str = "none"            # "hammer" | "bullish_engulfing" | ... | "none"
    candle_direction: str = "neutral"       # "bullish" | "bearish" | "neutral"
    candle_success_rate: float = 0.0
    summary: str = ""


# ---------------------------------------------------------------------------
# Padrões gráficos — funções de detecção individuais
# ---------------------------------------------------------------------------

def _detect_double_bottom(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Dois mínimos locais dentro de ±3%, separados por 20–60 barras, retração ≥5%."""
    idx = argrelmin(lows, order=5)[0]
    criteria_met = 0
    total_criteria = 3
    detail = "double_bottom: "

    if len(idx) < 2:
        return PatternResult("double_bottom", False, 0.0, "bullish", 0.64, 0.0, "menos de 2 mínimas locais")

    # Verifica todos os pares de mínimas
    for i in range(len(idx) - 1):
        for j in range(i + 1, len(idx)):
            bar_gap = idx[j] - idx[i]
            if not (20 <= bar_gap <= 60):
                continue
            low_i = lows[idx[i]]
            low_j = lows[idx[j]]
            if low_i == 0:
                continue
            pct_diff = abs(low_j / low_i - 1)
            if pct_diff > 0.03:
                continue
            # retração intermediária ≥5%
            mid_high = highs[idx[i]:idx[j]].max()
            retraction = (mid_high / max(low_i, low_j) - 1)
            criteria_met = 0
            if pct_diff <= 0.03:
                criteria_met += 1
            if 20 <= bar_gap <= 60:
                criteria_met += 1
            if retraction >= 0.05:
                criteria_met += 1
            if criteria_met == total_criteria:
                conf = criteria_met / total_criteria
                detail = f"lows em idx {idx[i]} e {idx[j]}, diff={pct_diff:.2%}, retração={retraction:.2%}"
                return PatternResult("double_bottom", True, conf, "bullish", 0.64, 7.0, detail)

    return PatternResult("double_bottom", False, criteria_met / total_criteria, "bullish", 0.64, 0.0, "pares não satisfazem todos os critérios")


def _detect_triple_bottom(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Três mínimas dentro de ±3%, separadas por 15–50 barras cada."""
    idx = argrelmin(lows, order=5)[0]
    total_criteria = 3

    if len(idx) < 3:
        return PatternResult("triple_bottom", False, 0.0, "bullish", 0.79, 0.0, "menos de 3 mínimas locais")

    for i in range(len(idx) - 2):
        for j in range(i + 1, len(idx) - 1):
            for k in range(j + 1, len(idx)):
                g1 = idx[j] - idx[i]
                g2 = idx[k] - idx[j]
                if not (15 <= g1 <= 50 and 15 <= g2 <= 50):
                    continue
                l1, l2, l3 = lows[idx[i]], lows[idx[j]], lows[idx[k]]
                ref = max(l1, l2, l3)
                if ref == 0:
                    continue
                spread = (max(l1, l2, l3) - min(l1, l2, l3)) / ref
                if spread > 0.03:
                    continue
                criteria_met = 3
                conf = criteria_met / total_criteria
                detail = f"lows em idx {idx[i]},{idx[j]},{idx[k]}, spread={spread:.2%}"
                return PatternResult("triple_bottom", True, conf, "bullish", 0.79, 9.0, detail)

    return PatternResult("triple_bottom", False, 0.0, "bullish", 0.79, 0.0, "nenhum trio satisfaz os critérios")


def _detect_inverted_head_shoulders(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Três mínimas: central é a menor (cabeça), ombros dentro de ±5%, neckline ±3%."""
    idx = argrelmin(lows, order=5)[0]
    total_criteria = 3

    if len(idx) < 3:
        return PatternResult("inverted_head_shoulders", False, 0.0, "bullish", 0.74, 0.0, "menos de 3 mínimas locais")

    for i in range(len(idx) - 2):
        for j in range(i + 1, len(idx) - 1):
            for k in range(j + 1, len(idx)):
                l_left = lows[idx[i]]
                l_head = lows[idx[j]]
                l_right = lows[idx[k]]
                if l_left == 0 or l_right == 0:
                    continue
                # cabeça deve ser a menor
                if not (l_head < l_left and l_head < l_right):
                    continue
                shoulders_diff = abs(l_left / l_right - 1)
                if shoulders_diff > 0.05:
                    continue
                # neckline: máximas entre ombro-cabeça e cabeça-ombro dentro de ±3%
                neck1 = highs[idx[i]:idx[j]].max()
                neck2 = highs[idx[j]:idx[k]].max()
                if neck1 == 0:
                    continue
                neck_diff = abs(neck1 / neck2 - 1)
                criteria_met = sum([
                    l_head < l_left and l_head < l_right,
                    shoulders_diff <= 0.05,
                    neck_diff <= 0.03,
                ])
                if criteria_met == total_criteria:
                    conf = criteria_met / total_criteria
                    detail = f"ombros={l_left:.2f}/{l_right:.2f}, cabeça={l_head:.2f}, neckline diff={neck_diff:.2%}"
                    return PatternResult("inverted_head_shoulders", True, conf, "bullish", 0.74, 8.0, detail)

    return PatternResult("inverted_head_shoulders", False, 0.0, "bullish", 0.74, 0.0, "sem IHS válido")


def _detect_rectangle_bottom(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Últimas 60 barras: ≥3 toques no suporte (low ±2%) e ≥2 na resistência (high ±2%), range ≤15%."""
    window = min(60, len(lows))
    w_lows = lows[-window:]
    w_highs = highs[-window:]
    total_criteria = 3

    if len(w_lows) < 20:
        return PatternResult("rectangle_bottom", False, 0.0, "bullish", 0.80, 0.0, "dados insuficientes")

    support = w_lows.min()
    resistance = w_highs.max()
    if support == 0:
        return PatternResult("rectangle_bottom", False, 0.0, "bullish", 0.80, 0.0, "suporte zero")

    total_range = (resistance / support - 1)
    support_touches = int(np.sum(np.abs(w_lows / support - 1) <= 0.02))
    resistance_touches = int(np.sum(np.abs(w_highs / resistance - 1) <= 0.02))

    criteria_met = sum([
        support_touches >= 3,
        resistance_touches >= 2,
        total_range <= 0.15,
    ])
    conf = criteria_met / total_criteria
    if criteria_met == total_criteria:
        detail = f"suporte={support:.2f} ({support_touches} toques), resistência={resistance:.2f} ({resistance_touches} toques), range={total_range:.2%}"
        return PatternResult("rectangle_bottom", True, conf, "bullish", 0.80, 8.0, detail)

    return PatternResult("rectangle_bottom", False, conf, "bullish", 0.80, 0.0, f"critérios: {criteria_met}/{total_criteria}")


def _detect_cup_with_handle(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Correlação da curva de fechamento (30–60 barras) com parábola ≥0.80 + retração 5–15% nas últimas 5–15 barras."""
    total_criteria = 2
    best_corr = 0.0

    for cup_len in range(30, min(61, len(closes) - 15)):
        cup = closes[-(cup_len + 15):-15]
        if len(cup) < 10:
            continue
        x = np.linspace(0, 1, len(cup))
        parabola = -(x - 0.5) ** 2  # parábola invertida normalizada
        parabola_norm = (parabola - parabola.mean()) / (parabola.std() + 1e-9)
        cup_norm = (cup - cup.mean()) / (cup.std() + 1e-9)
        corr = float(np.corrcoef(cup_norm, parabola_norm)[0, 1])
        best_corr = max(best_corr, corr)

    handle_window = closes[-15:]
    handle_retraction = 0.0
    if len(handle_window) >= 5 and handle_window[0] > 0:
        handle_retraction = (handle_window[0] - handle_window.min()) / handle_window[0]

    criteria_met = sum([
        best_corr >= 0.80,
        0.05 <= handle_retraction <= 0.15,
    ])
    conf = criteria_met / total_criteria

    if criteria_met == total_criteria:
        detail = f"correlação parábola={best_corr:.2f}, retração handle={handle_retraction:.2%}"
        return PatternResult("cup_with_handle", True, conf, "bullish", 0.61, 6.0, detail)

    return PatternResult("cup_with_handle", False, conf, "bullish", 0.61, 0.0, f"corr={best_corr:.2f}, retração={handle_retraction:.2%}")


def _detect_ascending_triangle(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Mínimas crescentes + máximas horizontais (30–60 barras)."""
    total_criteria = 2

    for window in range(30, min(61, len(closes))):
        w_lows = lows[-window:]
        w_highs = highs[-window:]
        if len(w_lows) < 10:
            continue
        x = np.arange(len(w_lows))
        # slope das mínimas > 0
        slope_lows = float(np.polyfit(x, w_lows, 1)[0])
        # desvio padrão das máximas ≤ 2% do preço médio
        mean_price = w_highs.mean()
        if mean_price == 0:
            continue
        std_highs_pct = w_highs.std() / mean_price

        criteria_met = sum([
            slope_lows > 0,
            std_highs_pct <= 0.02,
        ])
        if criteria_met == total_criteria:
            conf = 1.0
            detail = f"slope lows={slope_lows:.4f}, std highs={std_highs_pct:.2%}, window={window}"
            return PatternResult("ascending_triangle", True, conf, "bullish", 0.77, 7.0, detail)

    return PatternResult("ascending_triangle", False, 0.0, "bullish", 0.77, 0.0, "sem triângulo ascendente")


def _detect_falling_wedge(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Máximas e mínimas decrescentes com convergência (slope highs < slope lows < 0, janela 30–60)."""
    total_criteria = 3

    for window in range(30, min(61, len(closes))):
        w_lows = lows[-window:]
        w_highs = highs[-window:]
        if len(w_lows) < 10:
            continue
        x = np.arange(len(w_lows))
        slope_highs = float(np.polyfit(x, w_highs, 1)[0])
        slope_lows = float(np.polyfit(x, w_lows, 1)[0])

        criteria_met = sum([
            slope_highs < 0,
            slope_lows < 0,
            slope_highs < slope_lows,  # convergência: highs caem mais rápido que lows
        ])
        if criteria_met == total_criteria:
            conf = 1.0
            detail = f"slope highs={slope_highs:.4f}, slope lows={slope_lows:.4f}, window={window}"
            return PatternResult("falling_wedge", True, conf, "bullish", 0.68, 7.0, detail)

    return PatternResult("falling_wedge", False, 0.0, "bullish", 0.68, 0.0, "sem cunha descendente")


def _detect_descending_triangle(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Máximas decrescentes + mínimas horizontais — seta has_bearish_warning."""
    total_criteria = 2

    for window in range(30, min(61, len(closes))):
        w_lows = lows[-window:]
        w_highs = highs[-window:]
        if len(w_lows) < 10:
            continue
        x = np.arange(len(w_highs))
        slope_highs = float(np.polyfit(x, w_highs, 1)[0])
        mean_price = w_lows.mean()
        if mean_price == 0:
            continue
        std_lows_pct = w_lows.std() / mean_price

        criteria_met = sum([
            slope_highs < 0,
            std_lows_pct <= 0.02,
        ])
        if criteria_met == total_criteria:
            detail = f"slope highs={slope_highs:.4f}, std lows={std_lows_pct:.2%}, window={window}"
            return PatternResult("descending_triangle", True, 1.0, "bearish", 0.64, 0.0, detail)

    return PatternResult("descending_triangle", False, 0.0, "bearish", 0.64, 0.0, "sem triângulo descendente")


def _detect_head_shoulders_top(  # MELHORIA
    lows: np.ndarray,
    highs: np.ndarray,
    closes: np.ndarray,
) -> PatternResult:
    """Três máximas: central é a maior (cabeça), ombros dentro de ±5%, neckline ±3%."""
    idx = argrelmax(highs, order=5)[0]
    total_criteria = 3

    if len(idx) < 3:
        return PatternResult("head_shoulders_top", False, 0.0, "bearish", 0.89, 0.0, "menos de 3 máximas locais")

    for i in range(len(idx) - 2):
        for j in range(i + 1, len(idx) - 1):
            for k in range(j + 1, len(idx)):
                h_left = highs[idx[i]]
                h_head = highs[idx[j]]
                h_right = highs[idx[k]]
                if h_left == 0 or h_right == 0:
                    continue
                # cabeça deve ser a maior
                if not (h_head > h_left and h_head > h_right):
                    continue
                shoulders_diff = abs(h_left / h_right - 1)
                if shoulders_diff > 0.05:
                    continue
                # neckline
                neck1 = lows[idx[i]:idx[j]].min()
                neck2 = lows[idx[j]:idx[k]].min()
                if neck1 == 0:
                    continue
                neck_diff = abs(neck1 / neck2 - 1)
                criteria_met = sum([
                    h_head > h_left and h_head > h_right,
                    shoulders_diff <= 0.05,
                    neck_diff <= 0.03,
                ])
                if criteria_met == total_criteria:
                    detail = f"ombros={h_left:.2f}/{h_right:.2f}, cabeça={h_head:.2f}, neckline diff={neck_diff:.2%}"
                    return PatternResult("head_shoulders_top", True, 1.0, "bearish", 0.89, 0.0, detail)

    return PatternResult("head_shoulders_top", False, 0.0, "bearish", 0.89, 0.0, "sem H&S topo")


# ---------------------------------------------------------------------------
# Padrões de candle
# ---------------------------------------------------------------------------

def _detect_candle_pattern(df: pd.DataFrame) -> tuple[str, str, float]:  # MELHORIA
    """Analisa as últimas 3 barras. Retorna (candle_pattern, candle_direction, success_rate)."""
    if len(df) < 3:
        return "none", "neutral", 0.0

    tail = df.tail(3)
    o = tail["Open"].values
    h = tail["High"].values
    l = tail["Low"].values
    c = tail["Close"].values

    def _body(i): return abs(c[i] - o[i])
    def _range(i): return h[i] - l[i] if h[i] != l[i] else 1e-9
    def _upper_shadow(i): return h[i] - max(c[i], o[i])
    def _lower_shadow(i): return min(c[i], o[i]) - l[i]

    # doji (última barra)
    if _body(2) <= 0.05 * _range(2):
        return "doji", "neutral", 0.50

    # hammer
    body2 = _body(2)
    rng2 = _range(2)
    lower2 = _lower_shadow(2)
    upper2 = _upper_shadow(2)
    if body2 <= 0.30 * rng2 and lower2 >= 2 * body2 and upper2 <= 0.10 * rng2:
        return "hammer", "bullish", 0.60

    # inverted hammer
    if body2 <= 0.30 * rng2 and upper2 >= 2 * body2 and lower2 <= 0.10 * rng2:
        return "inverted_hammer", "bullish", 0.55

    # bullish engulfing (barra 1 bearish, barra 2 bullish)
    bar1_bearish = c[1] < o[1]
    bar2_bullish = c[2] > o[2]
    if bar1_bearish and bar2_bullish:
        body1 = abs(c[1] - o[1])
        # barra 2 engloba completamente a barra 1
        if o[2] <= min(c[1], o[1]) and c[2] >= max(c[1], o[1]):
            return "bullish_engulfing", "bullish", 0.63

    # bearish engulfing
    bar1_bullish = c[1] > o[1]
    bar2_bearish = c[2] < o[2]
    if bar1_bullish and bar2_bearish:
        if o[2] >= max(c[1], o[1]) and c[2] <= min(c[1], o[1]):
            return "bearish_engulfing", "bearish", 0.63

    # morning star: barra 0 bearish grande, barra 1 pequena/doji, barra 2 bullish fecha acima do meio da barra 0
    bar0_bearish = c[0] < o[0]
    bar2_bullish_ms = c[2] > o[2]
    bar1_small = _body(1) <= 0.30 * _range(0) if _range(0) > 0 else False
    mid_bar0 = (o[0] + c[0]) / 2
    if bar0_bearish and bar1_small and bar2_bullish_ms and c[2] > mid_bar0:
        return "morning_star", "bullish", 0.53

    # evening star: barra 0 bullish grande, barra 1 pequena, barra 2 bearish fecha abaixo do meio da barra 0
    bar0_bullish = c[0] > o[0]
    bar2_bearish_es = c[2] < o[2]
    bar1_small_es = _body(1) <= 0.30 * _range(0) if _range(0) > 0 else False
    mid_bar0_es = (o[0] + c[0]) / 2
    if bar0_bullish and bar1_small_es and bar2_bearish_es and c[2] < mid_bar0_es:
        return "evening_star", "bearish", 0.72

    return "none", "neutral", 0.0


# ---------------------------------------------------------------------------
# PatternEngine
# ---------------------------------------------------------------------------

class PatternEngine:  # MELHORIA
    def analyze(self, df: pd.DataFrame, asset_class: str = "equity_indices") -> PatternSnapshot:
        df = _normalize_df(df)
        if df is None or len(df) < 120:
            return PatternSnapshot(summary="Dados insuficientes para detecção de padrões (mínimo 120 barras).")

        closes = df["Close"].values.astype(float)
        highs = df["High"].values.astype(float)
        lows = df["Low"].values.astype(float)

        detectors = [
            _detect_double_bottom,
            _detect_triple_bottom,
            _detect_inverted_head_shoulders,
            _detect_rectangle_bottom,
            _detect_cup_with_handle,
            _detect_ascending_triangle,
            _detect_falling_wedge,
            _detect_descending_triangle,
            _detect_head_shoulders_top,
        ]

        results: list[PatternResult] = []
        has_bearish_warning = False

        for detector in detectors:
            try:
                result = detector(lows, highs, closes)
            except Exception:
                continue
            results.append(result)
            if result.detected and result.breakout_direction == "bearish":
                has_bearish_warning = True

        detected = [r for r in results if r.detected]
        aggregate = min(sum(r.pattern_score for r in detected), 10.0)

        best = None
        if detected:
            bullish = [r for r in detected if r.breakout_direction == "bullish"]
            if bullish:
                best = max(bullish, key=lambda r: r.pattern_score)
            else:
                best = max(detected, key=lambda r: r.success_rate)

        candle_pattern, candle_direction, candle_success_rate = _detect_candle_pattern(df)

        detected_names = [r.pattern_name for r in detected]
        summary_parts = []
        if detected_names:
            summary_parts.append(f"Padrões: {', '.join(detected_names)}.")
        if has_bearish_warning:
            summary_parts.append("ALERTA BEARISH detectado.")
        if candle_pattern != "none":
            summary_parts.append(f"Candle: {candle_pattern} ({candle_direction}).")
        summary = " ".join(summary_parts) if summary_parts else "Nenhum padrão relevante detectado."

        return PatternSnapshot(
            patterns_detected=results,
            best_pattern=best,
            aggregate_pattern_score=aggregate,
            has_bearish_warning=has_bearish_warning,
            candle_pattern=candle_pattern,
            candle_direction=candle_direction,
            candle_success_rate=candle_success_rate,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame | None:  # MELHORIA
    if df is None or df.empty:
        return None
    col_map = {c.lower(): c.title() for c in df.columns}
    df = df.rename(columns={c: c.title() for c in df.columns})
    required = {"Close", "High", "Low", "Open"}
    if not required.issubset(df.columns):
        # Try original casing
        return df if required.issubset(df.columns) else None
    return df.dropna(subset=["Close", "High", "Low"])
