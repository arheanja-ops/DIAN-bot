"""Test de la lógica de detección de 'sin disponibilidad' del scraper.

Usa un fake mínimo de la API de Playwright (page/locator) para ejercitar
_modal_no_availability sin abrir un navegador. Cubre los casos reales:
- ModalError con el texto de 'no se encontraron especialidades' -> sin disp.
- ModalSinCitas visible -> sin disp.
- Ningún modal visible -> hay que seguir (no es 'sin disp').
- El framework duplica nodos del modal (texto solo en uno de ellos).
"""
import pytest

from dian_bot.scraper import _modal_no_availability


class FakeButton:
    def __init__(self, exists: bool):
        self._exists = exists
        self.clicked = False

    async def count(self):
        return 1 if self._exists else 0

    @property
    def first(self):
        return self

    async def click(self, timeout=None):
        self.clicked = True


class FakeNode:
    def __init__(self, visible: bool, text: str = ""):
        self._visible = visible
        self._text = text

    async def is_visible(self):
        return self._visible

    async def inner_text(self):
        return self._text


class FakeLocator:
    """Representa page.locator("[pantalla='X']"): una colección de nodos."""

    def __init__(self, nodes, button_exists=True):
        self._nodes = nodes
        self._button = FakeButton(button_exists)

    async def count(self):
        return len(self._nodes)

    def nth(self, i):
        return self._nodes[i]

    def get_by_role(self, role, name=None):
        return self._button


class FakePage:
    def __init__(self, modals: dict):
        # modals: {"ModalError": [FakeNode, ...], "ModalSinCitas": [...]}
        self._modals = modals

    def locator(self, selector: str):
        for key, nodes in self._modals.items():
            if key in selector:
                return FakeLocator(nodes)
        return FakeLocator([])

    async def wait_for_timeout(self, ms):
        return None


@pytest.mark.asyncio
async def test_modal_error_sin_especialidades_es_sin_disponibilidad():
    page = FakePage(
        {
            "ModalError": [
                FakeNode(True, ""),  # nodo wrapper duplicado, sin texto
                FakeNode(
                    True,
                    "No se encontraron especialidades relacionadas según "
                    "los filtros seleccionados.",
                ),
            ],
            "ModalSinCitas": [FakeNode(False)],
        }
    )
    assert await _modal_no_availability(page) is True


@pytest.mark.asyncio
async def test_modal_sin_citas_visible_es_sin_disponibilidad():
    page = FakePage(
        {
            "ModalError": [FakeNode(False)],
            "ModalSinCitas": [FakeNode(True, "No hay horarios disponibles")],
        }
    )
    assert await _modal_no_availability(page) is True


@pytest.mark.asyncio
async def test_sin_modales_visibles_no_es_sin_disponibilidad():
    page = FakePage(
        {
            "ModalError": [FakeNode(False)],
            "ModalSinCitas": [FakeNode(False)],
        }
    )
    assert await _modal_no_availability(page) is False


@pytest.mark.asyncio
async def test_modal_error_visible_sin_texto_es_sin_disponibilidad():
    # Un ModalError visible sin texto legible también se trata como sin disp.
    page = FakePage(
        {
            "ModalError": [FakeNode(True, "")],
            "ModalSinCitas": [FakeNode(False)],
        }
    )
    assert await _modal_no_availability(page) is True
