from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR


SIGNALS_DIR = DATA_DIR / "signals"
SIGNALS_HISTORY_PATH = SIGNALS_DIR / "signals_history.csv"

SIGNAL_COLUMNS = [
    "date",
    "run_type",
    "symbol",
    "asset_class",
    "phase",
    "score",
    "classification",
    "close",
    "confirmation_trigger_value",
    "invalidation_level_value",
    "was_notified",
    "notification_reason",
    "alert_type",
    "created_at",
]

PHASE_RANKS = {
    "Tese invalidada": -1,
    "Fora do padrão": 0,
    "Fora do padrao": 0,
    "Queda extrema, mas sem fundo": 1,
    "Possível estabilização": 2,
    "Possivel estabilizacao": 2,
    "Acumulação inicial": 3,
    "Acumulacao inicial": 3,
    "Acumulação avançada": 4,
    "Acumulacao avancada": 4,
    "Rompimento inicial": 5,
    "Tese forte": 6,
}


def _ensure_history_file() -> None:
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    if not SIGNALS_HISTORY_PATH.exists():
        pd.DataFrame(columns=SIGNAL_COLUMNS).to_csv(SIGNALS_HISTORY_PATH, index=False)


def load_signal_history() -> pd.DataFrame:
    _ensure_history_file()
    return pd.read_csv(SIGNALS_HISTORY_PATH)


def save_signal_history(df: pd.DataFrame) -> None:
    _ensure_history_file()
    for column in SIGNAL_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df[SIGNAL_COLUMNS].to_csv(SIGNALS_HISTORY_PATH, index=False)


def append_signal_snapshot(results: list, run_type: str) -> None:
    history = load_signal_history()
    created_at = datetime.now().isoformat(timespec="seconds")
    rows = []
    for result in results:
        rows.append(
            {
                "date": result.get("date", ""),
                "run_type": run_type,
                "symbol": result.get("symbol", ""),
                "asset_class": result.get("asset_class", ""),
                "phase": result.get("phase", ""),
                "score": result.get("score", 0),
                "classification": result.get("classification", ""),
                "close": result.get("close", 0),
                "confirmation_trigger_value": result.get("confirmation_trigger_value", ""),
                "invalidation_level_value": result.get("invalidation_level_value", ""),
                "was_notified": bool(result.get("was_notified", False)),
                "notification_reason": result.get("notification_reason") or result.get("daily_alert_reason", ""),
                "alert_type": result.get("alert_type", ""),
                "created_at": created_at,
            }
        )
    if rows:
        history = pd.concat([history, pd.DataFrame(rows)], ignore_index=True)
        save_signal_history(history)


def get_previous_signal(symbol: str) -> dict | None:
    history = load_signal_history()
    if history.empty or "symbol" not in history.columns:
        return None
    matches = history[history["symbol"].astype(str).str.upper() == symbol.upper()]
    if matches.empty:
        return None
    return matches.iloc[-1].to_dict()


def get_phase_rank(phase: str) -> int:
    return PHASE_RANKS.get(phase, 0)


def detect_phase_change(current_phase: str, previous_phase: str | None) -> dict:
    if not previous_phase:
        return {
            "changed": True,
            "direction": "new",
            "previous_phase": None,
            "current_phase": current_phase,
            "message": "Novo ativo no radar.",
        }
    current_rank = get_phase_rank(current_phase)
    previous_rank = get_phase_rank(previous_phase)
    if current_phase == "Tese invalidada":
        direction = "down" if previous_phase != current_phase else "same"
        return {
            "changed": previous_phase != current_phase,
            "direction": direction,
            "previous_phase": previous_phase,
            "current_phase": current_phase,
            "message": "Tese invalidada após perda de suporte.",
        }
    if current_rank > previous_rank:
        return {
            "changed": True,
            "direction": "up",
            "previous_phase": previous_phase,
            "current_phase": current_phase,
            "message": f"Fase melhorou de {previous_phase} para {current_phase}.",
        }
    if current_rank < previous_rank:
        return {
            "changed": True,
            "direction": "down",
            "previous_phase": previous_phase,
            "current_phase": current_phase,
            "message": f"Fase piorou de {previous_phase} para {current_phase}.",
        }
    return {
        "changed": False,
        "direction": "same",
        "previous_phase": previous_phase,
        "current_phase": current_phase,
        "message": "Fase sem mudança.",
    }


def compare_signal_change(current_result: dict, previous_signal: dict | None) -> dict:
    previous_phase = None if previous_signal is None else str(previous_signal.get("phase", ""))
    phase_change = detect_phase_change(current_result.get("phase", ""), previous_phase)
    previous_score = None
    if previous_signal is not None and pd.notna(previous_signal.get("score")):
        previous_score = float(previous_signal.get("score", 0))
    current_score = float(current_result.get("score", 0) or 0)
    score_change = None if previous_score is None else current_score - previous_score
    return {
        "phase_change": phase_change,
        "previous_score": previous_score,
        "current_score": current_score,
        "score_change": score_change,
    }


def should_notify_with_history(result: dict, previous_signal: dict | None) -> tuple[bool, str]:
    comparison = compare_signal_change(result, previous_signal)
    phase_change = comparison["phase_change"]
    score_change = comparison["score_change"]
    current_phase = result.get("phase", "")
    current_score = float(result.get("score", 0) or 0)

    if previous_signal is None:
        result["alert_type"] = "Novo alerta"
        return True, "Novo ativo no radar."

    was_previously_notified = str(previous_signal.get("was_notified", "")).lower() in {"true", "1", "yes"}
    previous_phase = str(previous_signal.get("phase", ""))

    if phase_change["direction"] == "up":
        if previous_phase == "Acumulação avançada" and current_phase == "Rompimento inicial":
            result["alert_type"] = "Mudança de fase"
            return True, "Saiu de Acumulação avançada para Rompimento inicial."
        if previous_phase == "Rompimento inicial" and current_phase == "Tese forte":
            result["alert_type"] = "Tese forte"
            return True, "Saiu de Rompimento inicial para Tese forte."
        result["alert_type"] = "Mudança de fase"
        return True, phase_change["message"]

    if score_change is not None and score_change >= 8:
        result["alert_type"] = "Reforço da tese"
        return True, f"Score subiu {score_change:.0f} pontos desde o último registro."

    previous_rank = get_phase_rank(previous_phase)
    if previous_rank <= 1 and current_score >= 70:
        result["alert_type"] = "Reentrada no radar"
        return True, "Ativo voltou ao radar com score >= 70."

    if was_previously_notified and (score_change is None or abs(score_change) < 5) and not phase_change["changed"]:
        result["alert_type"] = "Sem novo alerta"
        return False, "Ativo já foi enviado recentemente, fase sem mudança e score parecido."

    result["alert_type"] = "Sem novo alerta"
    return False, "Sem novo gatilho relevante desde o último alerta."
