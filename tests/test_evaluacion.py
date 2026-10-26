"""
Tests de evaluacion — Parte 4 (runner de pytest)
Ejecuta cada uno de los 17 casos como test independiente.

Para correr:
  python -m pytest tests/test_evaluacion.py -v
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key-evaluacion")
sys.path.insert(0, str(Path(__file__).parent.parent))

import estados as estadospb
import agente as agentepb
from evaluacion import (
    c01, c02, c03, c04, c05, c06, c07, c08, c09, c10,
    c11, c12, c13, c14, c15, c16, c17, c18,
)


# ==========================================
# FIXTURE: estado limpio por test
# ==========================================

@pytest.fixture(autouse=True)
def estado_limpio(tmp_path, monkeypatch):
    estadospb.reset_estado("AUTO")
    agentepb._reclamos_registrados.clear()
    monkeypatch.setattr(agentepb, "RECLAMOS_PATH", tmp_path / "reclamos.json")
    yield
    estadospb.reset_estado("AUTO")
    agentepb._reclamos_registrados.clear()


# ==========================================
# CASOS C01–C17
# ==========================================

def test_c01_ventas_exitosa():
    c01()


def test_c02_ventas_sin_registros():
    c02()


def test_c03_ventas_fecha_invalida():
    c03()


def test_c04_documentacion_exitosa():
    c04()


def test_c05_reclamo_confirmado():
    c05()


def test_c06_reclamo_denegado():
    c06()


def test_c07_idempotencia_reclamo():
    c07()


def test_c08_falla_herramienta():
    c08()


def test_c09_lista_blanca():
    c09()


def test_c10_anti_prompt_injection():
    c10()


def test_c11_estado_human_bloquea():
    c11()


def test_c12_estado_blocked_total():
    c12()


def test_c13_suggest_con_aprobacion():
    c13()


def test_c14_suggest_sin_aprobacion():
    c14()


def test_c15_secuencia_estados_completa():
    c15()


def test_c16_abuso_solo_supervisor_desbloquea():
    c16()


def test_c17_ventas_extremos():
    c17()


def test_c18_cruce_auto_human_auto():
    c18()


# ==========================================
# TESTS: funciones auxiliares de evaluacion
# ==========================================

def test_limpiar_estado_reinicia_todo():
    from evaluacion import _limpiar_estado
    estadospb.transicionar("low_confidence", "sistema")
    agentepb._reclamos_registrados["fake_hash"] = "REC-9999"
    _limpiar_estado()
    assert estadospb.get_estado() == "AUTO"
    assert len(agentepb._reclamos_registrados) == 0


def test_check_pasa_con_aserciones_verdaderas():
    from evaluacion import _check
    resultado = _check({"a": True, "b": True})
    assert resultado == {"a": True, "b": True}


def test_check_falla_con_asercion_falsa():
    from evaluacion import _check, AsertionFallida
    with pytest.raises(AsertionFallida) as exc:
        _check({"ok": True, "falla": False})
    assert "falla" in str(exc.value)


def test_run_caso_captura_excepcion():
    from evaluacion import _run_caso, AsertionFallida
    def caso_que_falla():
        raise AsertionFallida("algo salio mal")
    resultado = _run_caso(caso_que_falla)
    assert resultado["pasado"] is False
    assert "algo salio mal" in resultado["error"]


def test_run_caso_captura_error_inesperado():
    from evaluacion import _run_caso
    def caso_con_excepcion():
        raise RuntimeError("error inesperado")
    resultado = _run_caso(caso_con_excepcion)
    assert resultado["pasado"] is False
    assert "RuntimeError" in resultado["error"]


def test_ventas_tmp_crea_archivo_legible():
    from evaluacion import _ventas_tmp, _VENTAS_TEST
    import json
    vp = _ventas_tmp(_VENTAS_TEST)
    try:
        datos = json.loads(vp.read_text(encoding="utf-8"))
        assert "2026-10-01" in datos
        assert datos["2026-10-01"]["entradas"] == 55
    finally:
        vp.unlink(missing_ok=True)


def test_reclamos_tmp_crea_archivo_vacio():
    from evaluacion import _reclamos_tmp
    import json
    rp = _reclamos_tmp()
    try:
        datos = json.loads(rp.read_text(encoding="utf-8"))
        assert datos == []
    finally:
        rp.unlink(missing_ok=True)


def test_casos_tienen_18_entradas():
    from evaluacion import CASOS
    assert len(CASOS) == 18


def test_todos_los_casos_tienen_id_unico():
    from evaluacion import CASOS
    ids = [c[0] for c in CASOS]
    assert len(ids) == len(set(ids))


# ==========================================
# TESTS: procesar_turno no llama a la API en HUMAN/BLOCKED
# ==========================================
# Verifican que la proteccion esta en el metodo, no solo en main().

_MOCK_RESP_LLM = {
    "choices": [{"message": {"content": "respuesta mock"}}],
    "usage":   {"prompt_tokens": 10, "completion_tokens": 5},
}
_MENSAJES_TEST = [
    {"role": "system", "content": "test"},
    {"role": "user",   "content": "hola"},
]


def test_procesar_turno_no_llama_api_en_human():
    estadospb.transicionar("operator_takeover", "operador")   # AUTO -> HUMAN
    with patch("agente._post_openai") as mock_api:
        resultado = agentepb.procesar_turno(list(_MENSAJES_TEST))
    mock_api.assert_not_called()
    assert resultado == ""


def test_procesar_turno_no_llama_api_en_blocked():
    estadospb.transicionar("abuse_detected", "sistema")       # AUTO -> BLOCKED
    with patch("agente._post_openai") as mock_api:
        resultado = agentepb.procesar_turno(list(_MENSAJES_TEST))
    mock_api.assert_not_called()
    assert resultado == ""


def test_procesar_turno_llama_api_en_auto():
    # En AUTO, procesar_turno SI debe llamar a la API.
    with patch("agente._post_openai", return_value=_MOCK_RESP_LLM) as mock_api:
        resultado = agentepb.procesar_turno(list(_MENSAJES_TEST))
    mock_api.assert_called_once()
    assert resultado == "respuesta mock"


def test_procesar_turno_llama_api_para_borrador_en_suggest():
    estadospb.transicionar("low_confidence", "sistema")       # AUTO -> SUGGEST
    with patch("agente._post_openai", return_value=_MOCK_RESP_LLM) as mock_api:
        resultado = agentepb.procesar_turno(list(_MENSAJES_TEST))
    mock_api.assert_called_once()   # SUGGEST si llama al LLM (modo borrador)
    assert resultado == "respuesta mock"
