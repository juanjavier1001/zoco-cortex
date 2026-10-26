"""
Tests unitarios — Parte 3: Máquina de estados IA-humano.
Verifica transiciones válidas, inválidas, restricciones de estado e integración.

Para correr:
  python -m pytest tests/test_estados.py -v
"""
import os
import sys
import json
import pytest
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key-solo-unit-tests")
sys.path.insert(0, str(Path(__file__).parent.parent))
import estados as estadospb

try:
    import agente as agentepb
    _AGENTE_DISPONIBLE = True
except ModuleNotFoundError as e:
    if e.name != "agente":
        raise  # agente.py existe pero le falta una dependencia — error real
    agentepb = None
    _AGENTE_DISPONIBLE = False

# Marca para tests que requieren agente (se activa en feature/agente)
_sin_agente = pytest.mark.skipif(
    not _AGENTE_DISPONIBLE,
    reason="agente.py no disponible aún — se verifica en feature/agente"
)


# ==========================================
# FIXTURE: estado limpio por test
# ==========================================

@pytest.fixture(autouse=True)
def estado_limpio():
    estadospb.reset_estado("AUTO")
    yield
    estadospb.reset_estado("AUTO")


@pytest.fixture(autouse=True)
def agente_limpio(monkeypatch, tmp_path):
    """Evita que los reclamos de un test contaminen los siguientes."""
    if not _AGENTE_DISPONIBLE:
        yield
        return
    agentepb._reclamos_registrados.clear()
    monkeypatch.setattr(agentepb, "RECLAMOS_PATH", tmp_path / "reclamos.json")
    yield
    agentepb._reclamos_registrados.clear()


# ==========================================
# TESTS: estado inicial
# ==========================================

def test_estado_inicial_es_auto():
    assert estadospb.get_estado() == "AUTO"


def test_historial_inicial_vacio():
    assert estadospb.get_historial() == []


# ==========================================
# TESTS: transiciones validas (13 definidas)
# ==========================================

def test_auto_operator_takeover():
    nuevo = estadospb.transicionar("operator_takeover", "operador")
    assert nuevo == "HUMAN"
    assert estadospb.get_estado() == "HUMAN"


def test_auto_customer_requests_human():
    nuevo = estadospb.transicionar("customer_requests_human", "sistema")
    assert nuevo == "HUMAN"


def test_auto_low_confidence():
    nuevo = estadospb.transicionar("low_confidence", "sistema")
    assert nuevo == "SUGGEST"


def test_auto_abuse_detected():
    nuevo = estadospb.transicionar("abuse_detected", "sistema")
    assert nuevo == "BLOCKED"


def test_suggest_operator_takeover():
    estadospb.transicionar("low_confidence", "sistema")
    nuevo = estadospb.transicionar("operator_takeover", "operador")
    assert nuevo == "HUMAN"


def test_suggest_operator_release():
    estadospb.transicionar("low_confidence", "sistema")
    nuevo = estadospb.transicionar("operator_release", "operador")
    assert nuevo == "AUTO"


def test_suggest_abuse_detected():
    estadospb.transicionar("low_confidence", "sistema")
    nuevo = estadospb.transicionar("abuse_detected", "sistema")
    assert nuevo == "BLOCKED"


def test_human_operator_release():
    estadospb.transicionar("operator_takeover", "operador")
    nuevo = estadospb.transicionar("operator_release", "operador")
    assert nuevo == "AUTO"


def test_human_abuse_detected():
    # Contradiccion C1: HUMAN + abuse_detected → BLOCKED (no HUMAN)
    estadospb.transicionar("operator_takeover", "operador")
    nuevo = estadospb.transicionar("abuse_detected", "sistema")
    assert nuevo == "BLOCKED"


def test_blocked_supervisor_unblock():
    estadospb.transicionar("abuse_detected", "sistema")
    nuevo = estadospb.transicionar("supervisor_unblock", "supervisor")
    assert nuevo == "AUTO"


def test_auto_out_of_hours_started():
    nuevo = estadospb.transicionar("out_of_hours_started", "sistema")
    assert nuevo == "AUTO"


def test_suggest_out_of_hours_started():
    estadospb.transicionar("low_confidence", "sistema")
    nuevo = estadospb.transicionar("out_of_hours_started", "sistema")
    assert nuevo == "AUTO"


def test_human_out_of_hours_started():
    estadospb.transicionar("operator_takeover", "operador")
    nuevo = estadospb.transicionar("out_of_hours_started", "sistema")
    assert nuevo == "AUTO"


# ==========================================
# TESTS: transiciones INVALIDAS (>= 3 requeridas)
# ==========================================

def test_blocked_operator_release_invalida():
    """C2: BLOCKED + operator_release no debe existir — solo supervisor desbloquea."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")
    # El estado no debe haber cambiado
    assert estadospb.get_estado() == "BLOCKED"


def test_blocked_out_of_hours_invalida():
    """C3: out_of_hours_started no aplica a BLOCKED."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.get_estado() == "BLOCKED"


def test_human_operator_takeover_invalida():
    """HUMAN + operator_takeover no está definido (ya está en control humano)."""
    estadospb.transicionar("operator_takeover", "operador")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_takeover", "operador")


def test_auto_operator_release_invalida():
    """AUTO + operator_release no está definido."""
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")


def test_blocked_operator_takeover_invalida():
    """BLOCKED + operator_takeover no está definido."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_takeover", "operador")


def test_blocked_low_confidence_invalida():
    """BLOCKED no acepta eventos que no sean supervisor_unblock."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("low_confidence", "sistema")


def test_evento_desconocido_falla():
    """Un evento que no existe en EVENTOS debe lanzar error."""
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("evento_inventado", "sistema")


def test_estado_no_cambia_en_transicion_invalida():
    """Tras una transición inválida el estado debe quedar igual."""
    assert estadospb.get_estado() == "AUTO"
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")
    assert estadospb.get_estado() == "AUTO"


# ==========================================
# TESTS: registro del historial
# ==========================================

def test_transicion_registra_historial():
    estadospb.transicionar("low_confidence", "sistema")
    hist = estadospb.get_historial()
    assert len(hist) == 1
    entrada = hist[0]
    assert entrada["estado_anterior"] == "AUTO"
    assert entrada["estado_nuevo"] == "SUGGEST"
    assert entrada["evento"] == "low_confidence"
    assert entrada["actor"] == "sistema"
    assert "fecha" in entrada


def test_historial_acumula_multiples_transiciones():
    estadospb.transicionar("low_confidence", "sistema")
    estadospb.transicionar("operator_takeover", "operador")
    estadospb.transicionar("operator_release", "operador")
    assert len(estadospb.get_historial()) == 3


def test_historial_no_registra_transicion_invalida():
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")
    assert len(estadospb.get_historial()) == 0


def test_guardar_historial(tmp_path):
    estadospb.transicionar("abuse_detected", "sistema")
    estadospb.transicionar("supervisor_unblock", "supervisor")
    path = tmp_path / "historial.json"
    estadospb.guardar_historial(path)
    datos = json.loads(path.read_text(encoding="utf-8"))
    assert len(datos) == 2
    assert datos[0]["evento"] == "abuse_detected"
    assert datos[1]["evento"] == "supervisor_unblock"


# ==========================================
# TESTS: reset_estado
# ==========================================

def test_reset_a_estado_valido():
    estadospb.transicionar("low_confidence", "sistema")
    estadospb.reset_estado("BLOCKED")
    assert estadospb.get_estado() == "BLOCKED"
    assert estadospb.get_historial() == []


def test_reset_estado_invalido_falla():
    with pytest.raises(ValueError):
        estadospb.reset_estado("INVALIDO")


# ==========================================
# TESTS: reglas del agente — puede_ejecutar_herramienta
# ==========================================

def test_auto_todas_herramientas_disponibles():
    assert estadospb.puede_ejecutar_herramienta("buscar_documentacion")
    assert estadospb.puede_ejecutar_herramienta("consultar_ventas")
    assert estadospb.puede_ejecutar_herramienta("crear_reclamo")


def test_suggest_herramientas_info_disponibles():
    estadospb.transicionar("low_confidence", "sistema")
    assert estadospb.puede_ejecutar_herramienta("buscar_documentacion")
    assert estadospb.puede_ejecutar_herramienta("consultar_ventas")


def test_suggest_crear_reclamo_no_libre():
    """En SUGGEST crear_reclamo no está libre — requiere aprobacion_operador."""
    estadospb.transicionar("low_confidence", "sistema")
    assert not estadospb.puede_ejecutar_herramienta("crear_reclamo")
    assert estadospb.requiere_aprobacion_operador("crear_reclamo")


def test_human_ninguna_herramienta_disponible():
    estadospb.transicionar("operator_takeover", "operador")
    assert not estadospb.puede_ejecutar_herramienta("buscar_documentacion")
    assert not estadospb.puede_ejecutar_herramienta("consultar_ventas")
    assert not estadospb.puede_ejecutar_herramienta("crear_reclamo")


def test_blocked_ninguna_herramienta_disponible():
    estadospb.transicionar("abuse_detected", "sistema")
    assert not estadospb.puede_ejecutar_herramienta("buscar_documentacion")
    assert not estadospb.puede_ejecutar_herramienta("crear_reclamo")


# ==========================================
# TESTS: puede_responder y genera_borrador
# ==========================================

def test_auto_puede_responder():
    assert estadospb.puede_responder()
    assert not estadospb.genera_borrador()


def test_suggest_puede_responder_con_borrador():
    estadospb.transicionar("low_confidence", "sistema")
    assert estadospb.puede_responder()
    assert estadospb.genera_borrador()


def test_human_no_puede_responder():
    estadospb.transicionar("operator_takeover", "operador")
    assert not estadospb.puede_responder()
    assert not estadospb.genera_borrador()


def test_blocked_no_puede_responder():
    estadospb.transicionar("abuse_detected", "sistema")
    assert not estadospb.puede_responder()


# ==========================================
# TESTS: contradicciones — verificar resoluciones
# ==========================================

def test_c1_human_abuse_va_a_blocked_no_human():
    """C1: HUMAN + abuse_detected debe ir a BLOCKED, no quedar en HUMAN."""
    estadospb.transicionar("operator_takeover", "operador")
    assert estadospb.get_estado() == "HUMAN"
    nuevo = estadospb.transicionar("abuse_detected", "sistema")
    assert nuevo == "BLOCKED", "Seguridad > operador: debe ser BLOCKED"
    assert estadospb.get_estado() == "BLOCKED"


def test_c2_blocked_solo_supervisor_desbloquea():
    """C2: operator_release desde BLOCKED debe fallar — solo supervisor."""
    estadospb.transicionar("abuse_detected", "sistema")
    assert estadospb.get_estado() == "BLOCKED"
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")
    # Solo supervisor_unblock funciona
    nuevo = estadospb.transicionar("supervisor_unblock", "supervisor")
    assert nuevo == "AUTO"


def test_c3_out_of_hours_no_rompe_blocked():
    """C3: out_of_hours_started no debe desbloquear BLOCKED."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.get_estado() == "BLOCKED"


# ==========================================
# TESTS: integracion con agentepb.ejecutar_herramienta
# ==========================================

@_sin_agente
def test_herramienta_bloqueada_en_human(monkeypatch, tmp_path):
    """En HUMAN, ejecutar_herramienta devuelve error de estado."""
    ventas_tmp = tmp_path / "ventas.json"
    ventas_tmp.write_text(json.dumps({"2026-10-15": {
        "entradas": 50, "bruto": 225000.0, "devoluciones": 0.0, "neto": 225000.0
    }}), encoding="utf-8")
    monkeypatch.setattr(agentepb, "VENTAS_PATH", ventas_tmp)

    estadospb.transicionar("operator_takeover", "operador")
    result = agentepb.ejecutar_herramienta("consultar_ventas", {"fecha": "2026-10-15"})
    assert "[ESTADO:HUMAN]" in result
    assert "HUMAN" in result


@_sin_agente
def test_herramienta_bloqueada_en_blocked(monkeypatch, tmp_path):
    """En BLOCKED, ninguna herramienta puede ejecutarse."""
    ventas_tmp = tmp_path / "ventas.json"
    ventas_tmp.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(agentepb, "VENTAS_PATH", ventas_tmp)

    estadospb.transicionar("abuse_detected", "sistema")
    result = agentepb.ejecutar_herramienta("buscar_documentacion", {"consulta": "test"})
    assert "[ESTADO:BLOCKED]" in result


@_sin_agente
def test_buscar_documentacion_libre_en_suggest(monkeypatch):
    """En SUGGEST, buscar_documentacion funciona sin aprobacion adicional."""
    estadospb.transicionar("low_confidence", "sistema")
    mock_resultados = [{"documento": "DOC-01", "tipo": "politica", "estado": "vigente",
                        "vigencia_desde": "2026-01-01", "vigencia_hasta": "2027-01-01",
                        "texto": "Contenido de prueba"}]
    monkeypatch.setattr(agentepb, "_buscar_rag", lambda *a, **kw: mock_resultados)
    result = agentepb.ejecutar_herramienta("buscar_documentacion", {"consulta": "comisiones"})
    assert "[ERROR]" not in result
    assert "[ESTADO:" not in result


@_sin_agente
def test_crear_reclamo_en_suggest_con_aprobacion(monkeypatch):
    """En SUGGEST, crear_reclamo requiere aprobacion del operador."""
    estadospb.transicionar("low_confidence", "sistema")
    # Operador aprueba
    monkeypatch.setattr(agentepb, "_aprobar_operador_reclamo", lambda n, a: True)
    monkeypatch.setattr(agentepb, "_confirmar_en_consola", lambda m, d: True)
    result = agentepb.ejecutar_herramienta("crear_reclamo", {
        "motivo": "cobro_incorrecto",
        "descripcion": "Descripcion de prueba para reclamo en estado SUGGEST"
    })
    assert "REC-" in result


@_sin_agente
def test_crear_reclamo_en_suggest_sin_aprobacion(monkeypatch):
    """En SUGGEST, si el operador NO aprueba, el reclamo no se ejecuta."""
    estadospb.transicionar("low_confidence", "sistema")
    # Operador rechaza
    monkeypatch.setattr(agentepb, "_aprobar_operador_reclamo", lambda n, a: False)
    monkeypatch.setattr(agentepb, "_confirmar_en_consola", lambda m, d: True)
    result = agentepb.ejecutar_herramienta("crear_reclamo", {
        "motivo": "cobro_incorrecto",
        "descripcion": "Descripcion de prueba para reclamo que debe rechazarse"
    })
    assert "[ESTADO:SUGGEST]" in result
    assert "no aprobo" in result.lower() or "no aprobó" in result.lower()
    assert len(agentepb._reclamos_registrados) == 0


@_sin_agente
def test_herramienta_inventada_rechazada_en_cualquier_estado():
    """La lista blanca opera antes que la verificacion de estado."""
    for est in ["AUTO", "SUGGEST", "HUMAN", "BLOCKED"]:
        estadospb.reset_estado(est)
        result = agentepb.ejecutar_herramienta("herramienta_maliciosa", {})
        assert "[ERROR]" in result
        assert "no esta disponible" in result.lower()


def test_crear_reclamo_auto_no_requiere_aprobacion_operador():
    """En AUTO, crear_reclamo no pasa por aprobacion de operador."""
    assert estadospb.get_estado() == "AUTO"
    assert not estadospb.requiere_aprobacion_operador("crear_reclamo")
    assert estadospb.puede_ejecutar_herramienta("crear_reclamo")


# ==========================================
# TESTS: secuencias de transicion realistas
# ==========================================

def test_secuencia_auto_suggest_human_auto():
    """Flujo completo: AUTO → SUGGEST → HUMAN → AUTO."""
    assert estadospb.get_estado() == "AUTO"
    estadospb.transicionar("low_confidence", "sistema")
    assert estadospb.get_estado() == "SUGGEST"
    estadospb.transicionar("operator_takeover", "operador")
    assert estadospb.get_estado() == "HUMAN"
    estadospb.transicionar("operator_release", "operador")
    assert estadospb.get_estado() == "AUTO"
    assert len(estadospb.get_historial()) == 3


def test_secuencia_abuse_y_recuperacion():
    """Abuso detectado y recuperacion solo por supervisor."""
    estadospb.transicionar("low_confidence", "sistema")
    estadospb.transicionar("operator_takeover", "operador")
    estadospb.transicionar("abuse_detected", "sistema")
    assert estadospb.get_estado() == "BLOCKED"

    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("operator_release", "operador")

    estadospb.transicionar("supervisor_unblock", "supervisor")
    assert estadospb.get_estado() == "AUTO"


def test_historial_completo_tiene_todos_campos():
    """Cada entrada del historial tiene los cinco campos requeridos."""
    estadospb.transicionar("abuse_detected", "sistema")
    estadospb.transicionar("supervisor_unblock", "supervisor")
    campos_req = {"estado_anterior", "estado_nuevo", "evento", "actor", "fecha"}
    for entrada in estadospb.get_historial():
        assert campos_req.issubset(set(entrada.keys()))


# ==========================================
# TESTS: autorizacion de actor — supervisor_unblock
# ==========================================

def test_supervisor_puede_desbloquear_con_actor_correcto():
    """actor='supervisor' puede disparar supervisor_unblock."""
    estadospb.transicionar("abuse_detected", "sistema")
    nuevo = estadospb.transicionar("supervisor_unblock", "supervisor")
    assert nuevo == "AUTO"


def test_operador_no_puede_disparar_supervisor_unblock():
    """actor='operador' debe ser rechazado por la maquina de estados."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError) as exc:
        estadospb.transicionar("supervisor_unblock", "operador")
    assert "supervisor" in str(exc.value).lower()
    assert estadospb.get_estado() == "BLOCKED"


def test_sistema_no_puede_disparar_supervisor_unblock():
    """actor='sistema' tampoco puede desbloquear."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("supervisor_unblock", "sistema")
    assert estadospb.get_estado() == "BLOCKED"


def test_actor_vacio_no_puede_desbloquear():
    """Un actor vacio no tiene privilegios de supervisor."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("supervisor_unblock", "")
    assert estadospb.get_estado() == "BLOCKED"


def test_actor_manipulado_case_no_puede_desbloquear():
    """El nombre 'SUPERVISOR' (mayusculas) no es equivalente a 'supervisor'."""
    estadospb.transicionar("abuse_detected", "sistema")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("supervisor_unblock", "SUPERVISOR")
    with pytest.raises(estadospb.TransicionInvalidaError):
        estadospb.transicionar("supervisor_unblock", "supervisor ")  # espacio extra
    assert estadospb.get_estado() == "BLOCKED"


def test_autorizacion_no_cambia_estado_en_rechazo():
    """Cuando el actor es rechazado, el estado debe quedar igual."""
    estadospb.transicionar("abuse_detected", "sistema")
    assert estadospb.get_estado() == "BLOCKED"
    try:
        estadospb.transicionar("supervisor_unblock", "operador")
    except estadospb.TransicionInvalidaError:
        pass
    assert estadospb.get_estado() == "BLOCKED"
    assert estadospb.get_historial()[-1]["evento"] == "abuse_detected"  # ultimo exitoso


# ==========================================
# TESTS: fuera del horario
# ==========================================

def test_flag_fuera_de_horario_inactivo_por_defecto():
    assert not estadospb.esta_fuera_de_horario()


def test_out_of_hours_activa_el_flag():
    estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.esta_fuera_de_horario()


def test_reset_estado_limpia_flag_fuera_de_horario():
    estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.esta_fuera_de_horario()
    estadospb.reset_estado("AUTO")
    assert not estadospb.esta_fuera_de_horario()


def test_horario_atencion_humana_esta_definido():
    """La constante no debe ser un string vacio."""
    assert estadospb.HORARIO_ATENCION_HUMANA
    assert len(estadospb.HORARIO_ATENCION_HUMANA) > 10


def test_flag_fuera_de_horario_desde_suggest():
    estadospb.transicionar("low_confidence", "sistema")
    estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.esta_fuera_de_horario()
    assert estadospb.get_estado() == "AUTO"


def test_flag_fuera_de_horario_desde_human():
    estadospb.transicionar("operator_takeover", "operador")
    estadospb.transicionar("out_of_hours_started", "sistema")
    assert estadospb.esta_fuera_de_horario()
    assert estadospb.get_estado() == "AUTO"


# ==========================================
# TESTS: _verificar_supervisor en agentepb
# ==========================================

@_sin_agente
def test_verificar_supervisor_pin_correcto(monkeypatch):
    monkeypatch.setattr(agentepb, "SUPERVISOR_PIN", "mipinsup")
    monkeypatch.setattr("builtins.input", lambda _: "mipinsup")
    assert agentepb._verificar_supervisor()


@_sin_agente
def test_verificar_supervisor_pin_incorrecto(monkeypatch):
    monkeypatch.setattr(agentepb, "SUPERVISOR_PIN", "mipinsup")
    monkeypatch.setattr("builtins.input", lambda _: "pinequivocado")
    assert not agentepb._verificar_supervisor()


@_sin_agente
def test_verificar_supervisor_sin_pin_configurado(monkeypatch):
    """Si SUPERVISOR_PIN esta vacio, el acceso siempre es denegado."""
    monkeypatch.setattr(agentepb, "SUPERVISOR_PIN", "")
    assert not agentepb._verificar_supervisor()  # no llama a input()
