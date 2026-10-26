"""
Máquina de estados IA-humano — Parte 3
Controla quién tiene el control de la conversación en cada turno.
Ejecutar demo: python estados.py
"""
import json
from datetime import datetime
from pathlib import Path

# ==========================================
# ETAPA 1: DEFINICION DE ESTADOS Y EVENTOS
# ==========================================
# Los cuatro estados posibles y los siete eventos que disparan transiciones.

# Horario de atención humana — configuración explícita.
# DOC-11 describe el modelo de atención pero no define franjas horarias;
# este valor debe actualizarse según el acuerdo de servicio de ZocoTickets.
HORARIO_ATENCION_HUMANA = "lunes a viernes de 9:00 a 18:00 (hora Argentina)"

ESTADOS = frozenset({"AUTO", "SUGGEST", "HUMAN", "BLOCKED"})

EVENTOS = frozenset({
    "operator_takeover",
    "customer_requests_human",
    "low_confidence",
    "abuse_detected",
    "operator_release",
    "supervisor_unblock",
    "out_of_hours_started",
})

# ==========================================
# ETAPA 2: TABLA DE TRANSICIONES
# ==========================================
# (estado_actual, evento) → estado_nuevo
#
# Contradicciones resueltas — detalle en SPEC_REVIEW.md:
#   C1: HUMAN + abuse_detected aparece dos veces en la tabla original
#       (→ BLOCKED y → HUMAN). Resolución: → BLOCKED.
#       Seguridad tiene prioridad sobre la decisión del operador.
#   C2: BLOCKED + operator_release estaba en la tabla, pero la regla dice
#       "solo supervisor puede desbloquear BLOCKED". Resolución: eliminada.
#       Solo supervisor_unblock opera desde BLOCKED.
#   C3: out_of_hours_started → AUTO desde "cualquier estado" rompería BLOCKED.
#       Resolución: no aplica desde BLOCKED.
#       El bloqueo por abuso no puede ser superado por cambio de horario.

TRANSICIONES: dict[tuple[str, str], str] = {
    ("AUTO",    "operator_takeover"):       "HUMAN",
    ("AUTO",    "customer_requests_human"): "HUMAN",
    ("AUTO",    "low_confidence"):          "SUGGEST",
    ("AUTO",    "abuse_detected"):          "BLOCKED",
    ("SUGGEST", "operator_takeover"):       "HUMAN",
    ("SUGGEST", "operator_release"):        "AUTO",
    ("SUGGEST", "abuse_detected"):          "BLOCKED",
    ("HUMAN",   "operator_release"):        "AUTO",
    ("HUMAN",   "abuse_detected"):          "BLOCKED",   # C1: BLOCKED gana
    ("BLOCKED", "supervisor_unblock"):      "AUTO",
    # out_of_hours_started: aplica a AUTO/SUGGEST/HUMAN pero NO a BLOCKED (C3)
    ("AUTO",    "out_of_hours_started"):    "AUTO",
    ("SUGGEST", "out_of_hours_started"):    "AUTO",
    ("HUMAN",   "out_of_hours_started"):    "AUTO",
}

# ==========================================
# ETAPA 3: ESTADO GLOBAL Y REGISTRO
# ==========================================
# Estado interno de la máquina y log de transiciones en memoria.
# El log puede persistirse en disco con guardar_historial().

_estado_actual: str = "AUTO"
_historial: list[dict] = []
_fuera_de_horario: bool = False   # True cuando out_of_hours_started fue disparado


class TransicionInvalidaError(Exception):
    """Transición no definida o actor no autorizado para el evento dado."""


def get_estado() -> str:
    """Devuelve el estado actual de la máquina."""
    return _estado_actual


def get_historial() -> list[dict]:
    """Devuelve copia del registro de transiciones."""
    return list(_historial)


def esta_fuera_de_horario() -> bool:
    """True si se disparó out_of_hours_started en esta sesión."""
    return _fuera_de_horario


def reset_estado(estado: str = "AUTO"):
    """Reinicia la máquina a un estado conocido. Usar solo en tests."""
    global _estado_actual, _fuera_de_horario
    if estado not in ESTADOS:
        raise ValueError(f"Estado desconocido: {estado!r}. Válidos: {sorted(ESTADOS)}")
    _estado_actual = estado
    _fuera_de_horario = False
    _historial.clear()


def guardar_historial(path: Path):
    """Persiste el log de transiciones en un archivo JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_historial, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _registrar(estado_ant: str, estado_nuevo: str, evento: str, actor: str):
    _historial.append({
        "estado_anterior": estado_ant,
        "estado_nuevo":    estado_nuevo,
        "evento":          evento,
        "actor":           actor,
        "fecha":           datetime.now().isoformat(timespec="seconds"),
    })


# ==========================================
# ETAPA 4: TRANSICIONES Y AUTORIZACION
# ==========================================
# transicionar() es el único punto de entrada para cambiar de estado.
# Toda transición no definida lanza TransicionInvalidaError.
# Ciertos eventos exigen que el actor tenga un rol autorizado.

# Eventos que requieren un rol específico de actor.
# En producción: el actor lo asigna el sistema de autenticación, nunca el usuario.
_ACTORES_REQUERIDOS: dict[str, frozenset[str]] = {
    "supervisor_unblock": frozenset({"supervisor"}),
}


def transicionar(evento: str, actor: str = "sistema") -> str:
    """
    Aplica un evento al estado actual.
    Retorna el nuevo estado.
    Lanza TransicionInvalidaError si la transición no está definida o
    si el actor no está autorizado para el evento.
    """
    global _estado_actual, _fuera_de_horario

    if evento not in EVENTOS:
        raise TransicionInvalidaError(
            f"Evento desconocido: {evento!r}. "
            f"Eventos válidos: {sorted(EVENTOS)}"
        )

    # Verificar autorización de actor antes de comprobar si la transición existe
    actores_req = _ACTORES_REQUERIDOS.get(evento)
    if actores_req and actor not in actores_req:
        raise TransicionInvalidaError(
            f"El evento '{evento}' requiere actor autorizado. "
            f"Actores permitidos: {sorted(actores_req)}. "
            f"Actor recibido: {actor!r}."
        )

    clave = (_estado_actual, evento)
    if clave not in TRANSICIONES:
        raise TransicionInvalidaError(
            f"Transición no definida: estado='{_estado_actual}' + evento='{evento}'. "
            "Esta combinación no está permitida."
        )
    nuevo = TRANSICIONES[clave]
    _registrar(_estado_actual, nuevo, evento, actor)
    _estado_actual = nuevo

    # Registrar que estamos fuera del horario de atención humana
    if evento == "out_of_hours_started":
        _fuera_de_horario = True

    return nuevo


# ==========================================
# ETAPA 5: REGLAS DE CONTROL DEL AGENTE
# ==========================================
# Estas funciones determinan qué puede hacer el agente según el estado actual.
# Son llamadas por agente.ejecutar_herramienta() para garantizar las políticas.

# Herramientas disponibles sin restricción adicional según el estado
_HERRAMIENTAS_LIBRES: dict[str, frozenset] = {
    "AUTO":    frozenset({"buscar_documentacion", "consultar_ventas", "crear_reclamo"}),
    # En SUGGEST: crear_reclamo no está aquí; requiere_aprobacion_operador() lo maneja
    "SUGGEST": frozenset({"buscar_documentacion", "consultar_ventas"}),
    "HUMAN":   frozenset(),    # agente completamente inactivo
    "BLOCKED": frozenset(),    # nadie responde
}


def puede_ejecutar_herramienta(nombre: str) -> bool:
    """True si la herramienta está disponible sin restricciones en el estado actual."""
    return nombre in _HERRAMIENTAS_LIBRES.get(get_estado(), frozenset())


def requiere_aprobacion_operador(nombre: str) -> bool:
    """En SUGGEST, crear_reclamo necesita aprobación explícita del operador."""
    return get_estado() == "SUGGEST" and nombre == "crear_reclamo"


def puede_responder() -> bool:
    """True si el agente puede generar y enviar una respuesta al cliente."""
    return get_estado() in ("AUTO", "SUGGEST")


def genera_borrador() -> bool:
    """True si la respuesta es un borrador que el operador debe aprobar."""
    return get_estado() == "SUGGEST"


def descripcion_estado() -> str:
    """Texto descriptivo del estado actual para mostrar en la interfaz."""
    estado = get_estado()
    desc = {
        "AUTO":    "IA responde automáticamente",
        "SUGGEST": "IA sugiere borradores — operador aprueba antes de enviar",
        "HUMAN":   "Operador controla — IA inactiva",
        "BLOCKED": "Bloqueada por abuso — solo supervisor desbloquea (!unblock)",
    }
    return f"[{estado}] {desc.get(estado, '')}"


# ==========================================
# ETAPA 6: EJECUCION (demo standalone)
# ==========================================
# Demo de la máquina sin el agente: muestra transiciones y el historial.

if __name__ == "__main__":
    print("=" * 58)
    print("  Máquina de estados IA-humano — Parte 3 (demo)")
    print("=" * 58)
    print(f"  Estado inicial: {descripcion_estado()}")
    print()
    print("  Transiciones definidas:")
    for (est, ev), nuevo in sorted(TRANSICIONES.items()):
        print(f"    {est:8s} + {ev:30s} -> {nuevo}")
    print()

    print("--- Secuencia de prueba ---")
    demos = [
        ("low_confidence",     "sistema"),    # AUTO → SUGGEST
        ("operator_takeover",  "operador"),   # SUGGEST → HUMAN
        ("operator_release",   "operador"),   # HUMAN → AUTO
        ("abuse_detected",     "sistema"),    # AUTO → BLOCKED
        ("operator_release",   "operador"),   # BLOCKED + op_release → ERROR (C2)
        ("supervisor_unblock", "supervisor"), # BLOCKED → AUTO
    ]
    for evento, actor in demos:
        antes = get_estado()
        try:
            nuevo = transicionar(evento, actor)
            print(f"  OK  {antes:8s} + {evento:30s} -> {nuevo}")
        except TransicionInvalidaError as e:
            print(f"  ERR {antes:8s} + {evento:30s} -> {e}")

    print()
    print("--- Historial registrado ---")
    for e in get_historial():
        print(
            f"  {e['fecha']}  "
            f"{e['estado_anterior']:8s} -> {e['estado_nuevo']:8s}  "
            f"[{e['evento']}] actor={e['actor']}"
        )
