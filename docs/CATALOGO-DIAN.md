# Catálogo DIAN: qué se puede monitorear / hacer

> Investigación 2026-09-11 sobre https://agendamiento.dian.gov.co/ y el ecosistema
> DIAN. Distingue lo que el bot **ya puede** hacer (monitoreo de citas) de lo que
> implicaría **otro tipo de automatización** (trámites transaccionales).

## 1. Sistema de AGENDAMIENTO DE CITAS (lo que el bot monitorea hoy)

Estructura real: `TipoPersona` × `TipoAtencion` × `Categoría` × `Trámite`.
Los trámites del combo `Servicios` aparecen/desaparecen según disponibilidad de
cupos en tiempo real (por eso "vuelan").

### Persona Natural · Presencial
- **RUT y orientación TAC** (5): Inscripción/actualización RUT persona natural;
  RUT sucesión ilíquida; RUT persona jurídica sin NIT; Libros de contabilidad;
  Orientación TAC.
- **Aduanas** (4): Corrección declaración importación SYGA; Creación/reactivación
  cuenta SYGA; Orientación exportación plan canguro; Orientación general aduanera.
- **Cobranzas** (2): Información cobranzas; Información sucesión.
- **Recaudo** (1): Corrección de inconsistencias en declaraciones/recibos.
- **Defensoría** (1): Atención defensoría.

### Persona Natural · Videoatención
- **RUT y orientación TAC** (3): RUT persona natural; RUT sucesión ilíquida;
  RUT persona jurídica sin NIT.
- **Conferencias/capacitaciones** (1): "Hablemos del RADIAN - Factura Electrónica".
- **Devoluciones** (0 ahora — el que monitoreas; aparece cuando abren cupos).
- **Autogestión NAF** (26): puntos NAF en universidades por ciudad.
- **Inconsistencias Grandes Contribuyentes** (0 ahora).
- **Cobranzas** (0 ahora).
- **Defensoría** (1).

### Persona Jurídica · Presencial / Videoatención
Similar, con menos trámites (ver `catalogo_dian.json` para el detalle completo).

**Todo lo anterior es MONITOREABLE por el bot actual** con solo cambiar la
configuración (categoría/trámite/persona/atención). Es el mismo scraper.

## 2. Otros servicios DIAN (NO son citas — otra clase de automatización)

Tu petición de "descargar facturas y todo lo demás" cae aquí. Estos **no** están
en el sistema de citas; son servicios transaccionales que viven en **otros
portales** y requieren **autenticación con las credenciales del contribuyente**:

| Servicio | Dónde | Requiere |
|---|---|---|
| Descargar factura electrónica / RADIAN | catalogo-vpfe.dian.gov.co | Login DIAN (usuario/clave o cert. digital) |
| Consultar/descargar RUT | muisca.dian.gov.co | Login DIAN |
| Declaraciones (renta, IVA, retención) | Muisca | Login DIAN + firma electrónica |
| Estado de cuenta / obligaciones | Muisca | Login DIAN |
| Consulta de terceros / RADIAN docs | catalogo-vpfe | Login DIAN |

### Diferencia crítica de alcance
- **Monitoreo de citas** (lo actual): solo lectura, sin login, sin datos
  sensibles. Bajo riesgo. El bot avisa; tú agendas.
- **Trámites transaccionales** (facturas, declaraciones): requieren **iniciar
  sesión con las credenciales fiscales del usuario**, manejar la **firma
  electrónica**, y operar sobre datos tributarios reales. Esto implica:
  - Custodiar credenciales DIAN del contribuyente (alto riesgo de seguridad).
  - Muisca tiene su propio flujo, sesiones, y a veces captcha/OTP.
  - Consideraciones legales: automatizar operaciones fiscales en nombre de
    alguien tiene implicaciones distintas a solo consultar disponibilidad.

**Recomendación:** tratar esto como un **proyecto/módulo separado** con su propio
diseño de seguridad (bóveda de credenciales, cifrado, consentimiento explícito),
no como una extensión trivial del bot de citas. Ver sección 3 del plan de
generalización.

## 3. Generalización del bot de citas (accionable ya, gratis)

El scraper actual está a un paso de monitorear **cualquier** trámite de citas:
- Hoy filtra por `DIAN_CATEGORIA=Devoluciones`.
- Generalizar = permitir una **lista de "watches"** (cada uno: persona, atención,
  categoría, y opcional filtro de trámite/ciudad), y notificar por cada match.

Ejemplo de configuración futura (una Lambda, varios watches):
```json
[
  {"persona":"Natural","atencion":"Videoatención","categoria":"Devoluciones"},
  {"persona":"Natural","atencion":"Presencial","categoria":"RUT y orientación TAC",
   "tramite":"Inscripción o actualización RUT persona natural"}
]
```
Esto es una extensión directa del código actual, sin nueva infraestructura.
