"""Tests del router del webhook de Telegram en lambda_handler.

Verifican el ruteo de comandos y la validación del secret token, mockeando el
envío a Telegram y la auto-invocación (sin red ni AWS).
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lambda_handler as lh


@pytest.fixture(autouse=True)
def _mocks(monkeypatch):
    sent = []
    invoked = []

    async def fake_send(chat_id, text):
        sent.append((chat_id, text))

    monkeypatch.setattr(lh, "_send", fake_send)
    monkeypatch.setattr(lh, "_self_invoke_scrape", lambda: invoked.append(True))
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    lh._sent = sent
    lh._invoked = invoked
    return sent, invoked


def _event(text, secret_header=None):
    ev = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {},
        "body": json.dumps({"message": {"text": text, "chat": {"id": 123}}}),
    }
    if secret_header is not None:
        ev["headers"]["x-telegram-bot-api-secret-token"] = secret_header
    return ev


def test_consultar_dispara_scrape_async(_mocks):
    sent, invoked = _mocks
    resp = lh._handle_webhook(_event("/consultar"))
    assert resp["statusCode"] == 200
    assert invoked == [True]  # se auto-invocó el scrape
    assert any("Consultando" in t for _, t in sent)


def test_ayuda_responde_help(_mocks):
    sent, _ = _mocks
    lh._handle_webhook(_event("/ayuda"))
    assert any("Comandos" in t for _, t in sent)


def test_comando_desconocido_responde_help(_mocks):
    sent, _ = _mocks
    lh._handle_webhook(_event("hola"))
    assert any("Comandos" in t for _, t in sent)


def test_secret_invalido_devuelve_403(monkeypatch, _mocks):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "esperado")
    resp = lh._handle_webhook(_event("/consultar", secret_header="incorrecto"))
    assert resp["statusCode"] == 403


def test_secret_valido_pasa(monkeypatch, _mocks):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "esperado")
    resp = lh._handle_webhook(_event("/ayuda", secret_header="esperado"))
    assert resp["statusCode"] == 200


def test_router_scrape_por_defecto(monkeypatch):
    # Evento sin marcadores de API Gateway -> acción scrape.
    called = {}
    monkeypatch.setattr(lh, "_run_scrape", lambda: called.setdefault("scrape", True) or {"statusCode": 200})
    monkeypatch.setattr(lh, "_load_secrets_from_ssm", lambda: None)
    lh.handler({"action": "scrape"}, None)
    assert called.get("scrape") is True
