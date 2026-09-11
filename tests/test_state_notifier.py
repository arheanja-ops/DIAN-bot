"""Tests de lógica pura: diff de estado y construcción de mensaje.

No dependen de red ni de navegador. Cubren las reglas de negocio críticas:
cuándo notificar y qué contiene el mensaje.
"""
from dian_bot.notifier import build_message, build_no_availability_message
from dian_bot.state import Availability, save, load_last, should_notify, append_history


def _av(available, slots=None, **kw):
    return Availability(
        available=available,
        servicio=kw.get("servicio", "Devolución IVA"),
        ciudad=kw.get("ciudad", "Medellín"),
        slots=slots or [],
        checked_at="2026-09-10T08:00:00-05:00",
    )


def test_no_disponible_nunca_notifica():
    assert should_notify(None, _av(False)) is False
    assert should_notify(_av(True, ["10:00"]), _av(False)) is False


def test_primera_disponibilidad_notifica():
    assert should_notify(None, _av(True, ["10:00"])) is True


def test_misma_disponibilidad_no_renotifica():
    prev = _av(True, ["10:00", "11:00"])
    curr = _av(True, ["11:00", "10:00"])  # mismo set, distinto orden
    assert should_notify(prev, curr) is False


def test_disponibilidad_cambiada_renotifica():
    prev = _av(True, ["10:00"])
    curr = _av(True, ["10:00", "12:00"])
    assert should_notify(prev, curr) is True


def test_aparece_disponibilidad_tras_vacio_notifica():
    prev = _av(False)
    curr = _av(True, ["09:30"])
    assert should_notify(prev, curr) is True


def test_persistencia_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    av = _av(True, ["08:30", "09:00"])
    save(path, av)
    loaded = load_last(path)
    assert loaded is not None
    assert loaded.available is True
    assert loaded.slots == ["08:30", "09:00"]
    assert loaded.signature() == av.signature()


def test_load_inexistente_devuelve_none(tmp_path):
    assert load_last(str(tmp_path / "nope.json")) is None


def test_mensaje_incluye_datos_clave():
    msg = build_message(
        _av(True, ["Bogotá - Solicitud de devolución", "Cali - Solicitud de devolución"]),
        "https://agendamiento.dian.gov.co/",
    )
    assert "Bogotá" in msg
    assert "Cali" in msg
    assert "agendamiento.dian.gov.co" in msg


def test_mensaje_urgente_dice_entra_ya_y_url():
    msg = build_message(_av(True, ["Cali - Solicitud de devolución"]), "https://agendamiento.dian.gov.co/")
    assert "ENTRA YA" in msg.upper()
    assert "agendamiento.dian.gov.co" in msg
    assert "Cali" in msg


def test_mensaje_sin_citas_es_informativo():
    msg = build_no_availability_message(_av(False))
    assert "sin citas" in msg.lower()
    assert "ENTRA YA" not in msg.upper()


def test_append_history_agrega_lineas(tmp_path):
    import json

    path = str(tmp_path / "history.jsonl")
    append_history(path, _av(False))
    append_history(path, _av(True, ["08:30"]))
    lines = [ln for ln in open(path, encoding="utf-8").read().splitlines() if ln]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["available"] is False
    assert second["available"] is True
    assert second["slots"] == ["08:30"]
