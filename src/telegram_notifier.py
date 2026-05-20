from __future__ import annotations

from dataclasses import dataclass
import os

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class TelegramSendResult:
    called: bool
    success: bool
    status_code: int | None = None
    response_text: str = ""
    error: str = ""

    def api_status(self) -> str:
        if not self.called:
            return self.error or "Telegram API not called."
        if self.status_code is None:
            return self.error or "Telegram API called, no HTTP status returned."
        if not self.response_text:
            return f"HTTP {self.status_code}"
        try:
            payload = requests.models.complexjson.loads(self.response_text)
        except ValueError:
            return f"HTTP {self.status_code}: {self.response_text[:300]}"
        ok = payload.get("ok")
        description = payload.get("description")
        message_id = (payload.get("result") or {}).get("message_id")
        if message_id:
            return f"HTTP {self.status_code}: ok={ok} message_id={message_id}"
        if description:
            return f"HTTP {self.status_code}: ok={ok} description={description}"
        return f"HTTP {self.status_code}: ok={ok}"


def send_telegram_message(message: str) -> bool:
    return send_telegram_message_detailed(message).success


def send_telegram_message_detailed(message: str) -> TelegramSendResult:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        error = "Erro: TELEGRAM_BOT_TOKEN nao encontrado no .env"
        print(error)
        return TelegramSendResult(called=False, success=False, error=error)

    if not chat_id:
        error = "Erro: TELEGRAM_CHAT_ID nao encontrado no .env"
        print(error)
        return TelegramSendResult(called=False, success=False, error=error)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        result = TelegramSendResult(
            called=True,
            success=response.status_code == 200,
            status_code=response.status_code,
            response_text=response.text,
        )

        if response.status_code != 200:
            print("Erro ao enviar mensagem para Telegram:")
            print(response.text)
            return result

        print("Mensagem enviada para o Telegram.")
        return result

    except Exception as error:
        message_error = f"Falha ao enviar mensagem para Telegram: {_redact_token(str(error), bot_token)}"
        print(message_error)
        return TelegramSendResult(called=True, success=False, error=message_error)


def _redact_token(value: str, bot_token: str | None) -> str:
    if not bot_token:
        return value
    return value.replace(bot_token, "***TOKEN_REDACTED***")


def format_screener_summary(results: list[dict]) -> str:
    if not results:
        return "Desbasement Agent V2\n\nNenhum ativo aprovado no screener."

    lines = ["Desbasement Agent V2", "", "Ativos aprovados:"]
    for result in results:
        lines.append(
            "- {symbol} | {phase} | score {score}/100 | gatilho: {trigger}".format(
                symbol=result.get("symbol", ""),
                phase=result.get("phase", ""),
                score=result.get("score", 0),
                trigger=result.get("confirmation_trigger", ""),
            )
        )
    return "\n".join(lines)
