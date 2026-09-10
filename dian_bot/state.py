"""Persistencia del último resultado de disponibilidad y cálculo de diff.

Guarda un JSON simple para no re-notificar la misma disponibilidad en cada
corrida. Diseñado para transparencia (file-based state).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Availability:
    """Resultado de una consulta de disponibilidad."""

    available: bool
    servicio: str
    ciudad: str
    # Fechas/horas detectadas (si las hay), como strings legibles
    slots: list[str] = field(default_factory=list)
    checked_at: str = ""
    note: str = ""

    def signature(self) -> str:
        """Firma estable del estado para comparar entre corridas."""
        return json.dumps(
            {"available": self.available, "slots": sorted(self.slots)},
            ensure_ascii=False,
            sort_keys=True,
        )


def load_last(path: str) -> Availability | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return Availability(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def save(path: str, av: Availability) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(asdict(av), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def should_notify(prev: Availability | None, current: Availability) -> bool:
    """Notificar solo si HAY disponibilidad y el estado cambió respecto al previo.

    - Sin disponibilidad -> nunca notifica (evita ruido diario).
    - Con disponibilidad y firma distinta a la previa -> notifica.
    - Con disponibilidad y misma firma que la previa -> no re-notifica.
    """
    if not current.available:
        return False
    if prev is None:
        return True
    return prev.signature() != current.signature()


def append_history(path: str, av: Availability) -> None:
    """Agrega el resultado a un histórico JSONL (una línea por consulta).

    Sirve para analizar el patrón temporal de liberación de citas (p. ej. si la
    DIAN abre cupos en fin de semana o de madrugada). No falla si el directorio
    no existe: lo crea.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(av), ensure_ascii=False, sort_keys=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
