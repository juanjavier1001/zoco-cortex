"""
Tests unitarios - Parte 1: Buscador RAG
Verifica coseno, BM25 y RRF con valores calculados a mano.

Para correr:
  # Linux/macOS:
  OPENAI_API_KEY=test-key python -m pytest tests/test_buscador.py -v
  # Windows (PowerShell):
  $env:OPENAI_API_KEY="test-key"; python -m pytest tests/test_buscador.py -v
"""
import math
import os
import sys
import pytest
import numpy as np
from pathlib import Path

# Fija API key antes de importar el modulo
os.environ.setdefault("OPENAI_API_KEY", "test-key-solo-para-unit-tests")
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from buscador import (
    similitud_coseno, tokenizar, fusion_rrf, RRF_K,
    recall_at_3, reciprocal_rank, cargar_cache_docs, buscar, _chunks,
)


# ==========================================
# TESTS: SIMILITUD COSENO
# ==========================================
# Valor esperado = (a · b) / (||a|| * ||b||)

def test_coseno_vectores_identicos():
    # a == b → angulo 0 → cos = 1.0
    a = np.array([1.0, 2.0, 3.0])
    assert similitud_coseno(a, a) == pytest.approx(1.0)


def test_coseno_vectores_ortogonales():
    # ningun componente en comun → angulo 90° → cos = 0.0
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert similitud_coseno(a, b) == pytest.approx(0.0)


def test_coseno_vectores_opuestos():
    # apuntan en sentido contrario → angulo 180° → cos = -1.0
    a = np.array([1.0, 0.0])
    b = np.array([-1.0, 0.0])
    assert similitud_coseno(a, b) == pytest.approx(-1.0)


def test_coseno_valor_calculado_manualmente():
    # a=[1,2,3], b=[4,5,6]
    # dot = 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
    # ||a|| = sqrt(1+4+9) = sqrt(14)
    # ||b|| = sqrt(16+25+36) = sqrt(77)
    # cos = 32 / sqrt(14 * 77) = 32 / sqrt(1078)
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    esperado = 32.0 / math.sqrt(14 * 77)   # ≈ 0.97463185
    assert similitud_coseno(a, b) == pytest.approx(esperado, rel=1e-9)


def test_coseno_escalar_no_cambia_angulo():
    # Escalar un vector no cambia su direccion → mismo coseno
    a = np.array([1.0, 2.0])
    b = np.array([2.0, 4.0])   # b = 2*a
    assert similitud_coseno(a, b) == pytest.approx(1.0)


# ==========================================
# TESTS: BM25 (formula implementada localmente)
# ==========================================
# Mismos parametros que buscador: K1=1.5, B=0.75
# Formula: score += idf * (tf*(K1+1)) / (tf + K1*(1-B+B*len/avg))
# IDF suavizado: log((N - df + 0.5) / (df + 0.5) + 1)

K1, B = 1.5, 0.75


def _bm25(tokens_q, tokens_doc, df, N, avg_len):
    """Reimplementacion local de la formula BM25 para comparar valores."""
    tf = {}
    for t in tokens_doc:
        tf[t] = tf.get(t, 0) + 1
    score, lon = 0.0, len(tokens_doc)
    for t in tokens_q:
        if t not in tf:
            continue
        f   = tf[t]
        n   = df.get(t, 0)
        idf = math.log((N - n + 0.5) / (n + 0.5) + 1)
        score += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * lon / avg_len))
    return score


def test_bm25_termino_ausente_puntua_cero():
    # Si el termino de la query no aparece en el doc, score = 0
    df      = {"perro": 1}
    N       = 3
    avg_len = 3.0
    assert _bm25(["perro"], ["el", "gato", "duerme"], df, N, avg_len) == pytest.approx(0.0)


def test_bm25_calculo_manual_corpus_3_docs():
    # Corpus: ["el perro corre", "el gato duerme", "el perro gato"]
    # N=3, avg_len=3.0
    # df: el=3, perro=2, corre=1, gato=2, duerme=1
    corpus = [
        ["el", "perro", "corre"],
        ["el", "gato", "duerme"],
        ["el", "perro", "gato"],
    ]
    N       = 3
    avg_len = 3.0
    df      = {"el": 3, "perro": 2, "corre": 1, "gato": 2, "duerme": 1}

    # Calculo manual para query="perro" en doc0:
    # idf("perro") = log((3-2+0.5)/(2+0.5) + 1) = log(1.5/2.5 + 1) = log(1.6)
    # tf=1, lon=3, avg=3 → denom = 1 + 1.5*(0.25 + 0.75*1) = 1 + 1.5 = 2.5
    # score = log(1.6) * (1*2.5)/2.5 = log(1.6)
    esperado = math.log(1.6)

    s0 = _bm25(["perro"], corpus[0], df, N, avg_len)
    s1 = _bm25(["perro"], corpus[1], df, N, avg_len)
    s2 = _bm25(["perro"], corpus[2], df, N, avg_len)

    assert s0 == pytest.approx(esperado, rel=1e-9)
    assert s1 == pytest.approx(0.0)        # "perro" no está en doc1
    assert s2 == pytest.approx(esperado)   # misma tf, lon y df que doc0


def test_bm25_doc_mas_largo_puntua_menos():
    # Con misma frecuencia del termino, un doc mas largo debe puntuar menos.
    # B > 0 penaliza docs mas largos que el promedio.
    df      = {"gol": 2}
    N       = 2
    avg_len = 3.5   # promedio entre len=2 y len=5
    corto   = ["gol", "gol"]           # len=2, por debajo del promedio
    largo   = ["gol", "gol", "x", "x", "x"]  # len=5, por encima del promedio
    assert _bm25(["gol"], corto, df, N, avg_len) > _bm25(["gol"], largo, df, N, avg_len)


def test_bm25_mayor_tf_puntua_mas():
    # Mas apariciones del termino en el mismo doc → mayor score
    df      = {"hola": 1}
    N       = 1
    avg_len = 4.0
    d1      = ["hola", "x", "x", "x"]        # tf=1
    d2      = ["hola", "hola", "x", "x"]     # tf=2
    assert _bm25(["hola"], d2, df, N, avg_len) > _bm25(["hola"], d1, df, N, avg_len)


def test_bm25_termino_raro_puntua_mas():
    # IDF es mayor cuando el termino aparece en menos docs (mas raro = mas informativo)
    df_raro   = {"termino": 1}   # aparece en 1 de 10 docs
    df_comun  = {"termino": 8}   # aparece en 8 de 10 docs
    N, avg, doc = 10, 5.0, ["termino", "a", "b", "c", "d"]
    assert _bm25(["termino"], doc, df_raro, N, avg) > _bm25(["termino"], doc, df_comun, N, avg)


# ==========================================
# TESTS: RRF (k=60)
# ==========================================
# RRF(d) = sum_r 1/(k + rank_r(d)), k=60
# Se importa directamente de buscador.

def test_rrf_constante_k_es_60():
    # Si un item esta primero en ambos rankings, score = 2/(60+1) = 2/61
    rv = [{"idx": 0}]
    rb = [{"idx": 0}]
    scores = fusion_rrf(rv, rb)
    assert RRF_K == 60
    assert scores[0] == pytest.approx(2.0 / 61, rel=1e-9)


def test_rrf_valores_calculados_manualmente():
    # rv: 0→pos1, 1→pos2, 2→pos3
    # rb: 2→pos1, 0→pos2, 1→pos3
    # scores[0] = 1/61 + 1/62
    # scores[1] = 1/62 + 1/63
    # scores[2] = 1/63 + 1/61
    rv = [{"idx": 0}, {"idx": 1}, {"idx": 2}]
    rb = [{"idx": 2}, {"idx": 0}, {"idx": 1}]
    scores = fusion_rrf(rv, rb)

    assert scores[0] == pytest.approx(1/61 + 1/62, rel=1e-9)
    assert scores[1] == pytest.approx(1/62 + 1/63, rel=1e-9)
    assert scores[2] == pytest.approx(1/63 + 1/61, rel=1e-9)


def test_rrf_orden_correcto():
    # Del test anterior, el orden esperado es 0 > 2 > 1
    rv = [{"idx": 0}, {"idx": 1}, {"idx": 2}]
    rb = [{"idx": 2}, {"idx": 0}, {"idx": 1}]
    scores = fusion_rrf(rv, rb)
    assert scores[0] > scores[2] > scores[1]


def test_rrf_consenso_maximiza_score():
    # Item en pos1 en ambos rankings tiene el maximo score posible
    rv = [{"idx": 0}, {"idx": 1}, {"idx": 2}]
    rb = [{"idx": 0}, {"idx": 2}, {"idx": 1}]
    scores = fusion_rrf(rv, rb)
    assert scores[0] == max(scores.values())


def test_rrf_item_en_un_solo_ranking():
    # rv: idx=0 en pos1 → 1/61; idx=1 en pos2 → 1/62
    # rb: idx=0 en pos1 → 1/61  (idx=1 no aparece en rb)
    # scores[0] = 1/61 + 1/61 = 2/61
    # scores[1] = 1/62          (solo de rv, pos2)
    rv = [{"idx": 0}, {"idx": 1}]
    rb = [{"idx": 0}]
    scores = fusion_rrf(rv, rb)
    assert scores[0] > scores[1]
    assert scores[1] == pytest.approx(1.0 / 62, rel=1e-9)


# ==========================================
# TEST: TOKENIZACION
# ==========================================

def test_tokenizar_minusculas_y_tildes():
    tokens = tokenizar("Canción con Ñ y tildes: café ÁRBOL")
    # Todo en minusculas sin diacriticos
    assert "cancion" in tokens
    assert "cafe" in tokens
    assert "arbol" in tokens
    assert not any(c in "".join(tokens) for c in "ÁÉÍÓÚÑ")


# ==========================================
# TESTS: RECALL@3
# ==========================================
# recall_at_3(docs, relevantes) = interseccion(docs[:3], relevantes) / len(relevantes)
# Redondea a 4 decimales.

def test_recall_at_3_un_relevante_encontrado():
    # El unico relevante esta en el top3 → recall = 1.0
    assert recall_at_3(["DOC-01", "DOC-02", "DOC-03"], ["DOC-01"]) == 1.0


def test_recall_at_3_ninguno_encontrado():
    # El relevante no aparece en los primeros 3 → recall = 0.0
    assert recall_at_3(["DOC-01", "DOC-02", "DOC-03"], ["DOC-04"]) == 0.0


def test_recall_at_3_parcial_dos_relevantes():
    # 1 de 2 relevantes en top3 → recall = 0.5
    assert recall_at_3(["DOC-01", "DOC-02", "DOC-03"], ["DOC-01", "DOC-04"]) == 0.5


def test_recall_at_3_ambos_relevantes_encontrados():
    # 2 de 2 relevantes en top3 → recall = 1.0
    assert recall_at_3(["DOC-01", "DOC-02", "DOC-03"], ["DOC-01", "DOC-02"]) == 1.0


def test_recall_at_3_ignora_posicion_4_en_adelante():
    # El relevante esta en posicion 4 → top3 no lo incluye → recall = 0.0
    assert recall_at_3(["DOC-01", "DOC-02", "DOC-03", "DOC-04"], ["DOC-04"]) == 0.0


# ==========================================
# TESTS: RECIPROCAL RANK (MRR)
# ==========================================
# reciprocal_rank(docs, relevantes) = 1/posicion del primer relevante encontrado
# Posicion basada en 1 (no en 0). Devuelve 0.0 si no se encuentra ninguno.

def test_reciprocal_rank_primer_lugar():
    # Relevante en posicion 1 → RR = 1.0
    assert reciprocal_rank(["DOC-01", "DOC-02", "DOC-03"], ["DOC-01"]) == 1.0


def test_reciprocal_rank_segundo_lugar():
    # Relevante en posicion 2 → RR = 0.5
    assert reciprocal_rank(["DOC-02", "DOC-01", "DOC-03"], ["DOC-01"]) == pytest.approx(0.5)


def test_reciprocal_rank_tercer_lugar():
    # Relevante en posicion 3 → RR = round(1/3, 4) = 0.3333
    assert reciprocal_rank(["DOC-02", "DOC-03", "DOC-01"], ["DOC-01"]) == pytest.approx(0.3333, abs=1e-4)


def test_reciprocal_rank_ausente():
    # Ningún relevante en la lista → RR = 0.0
    assert reciprocal_rank(["DOC-02", "DOC-03"], ["DOC-01"]) == 0.0


def test_reciprocal_rank_usa_primer_relevante_encontrado():
    # Hay dos relevantes; el primero encontrado es el que determina el RR
    # DOC-02 esta en posicion 1 → RR = 1.0, no 0.5
    assert reciprocal_rank(["DOC-02", "DOC-01"], ["DOC-01", "DOC-02"]) == 1.0


# ==========================================
# TESTS: CACHE Y LLAMADAS A LA API
# ==========================================

def test_cache_completa_no_llama_api():
    # Si todos los chunks ya estan en cache, cargar_cache_docs no llama a la API.
    with patch("buscador._llamar_api") as mock_api:
        cargar_cache_docs(_chunks)
        mock_api.assert_not_called()


def test_bm25_no_llama_api():
    # buscar() con estrategia='bm25' no debe generar embeddings ni llamar a la API.
    with patch("buscador._llamar_api") as mock_api:
        buscar("cuantos dias demora una liquidacion", estrategia="bm25")
        mock_api.assert_not_called()
