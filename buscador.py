import os
import re
import json
import math
import hashlib
import unicodedata
import urllib.request
import numpy as np
from pathlib import Path
from datetime import date

# ------------------------------------------------------------------
# CONFIGURACION
# ------------------------------------------------------------------
RAIZ       = Path(__file__).resolve().parent
DOCS       = RAIZ / "docs"
CACHE_DOCS = RAIZ / "cache" / "embeddings.json"
CACHE_QS   = RAIZ / "cache" / "embeddings_preguntas.json"
QUESTIONS  = RAIZ / "questions.jsonl"
RESULTADOS = RAIZ / "resultados" / "evaluacion.json"
MODELO     = "text-embedding-3-small"
API_KEY    = os.getenv("OPENAI_API_KEY")

K1, B, RRF_K = 1.5, 0.75, 60
HOY = date.today()
FACTOR_VIGENCIA = {"vigente": 1.00, "expirado": 0.75, "pendiente": 0.90}
# README — limitación conocida: penaliza docs expirados con info histórica relevante.
# Q17 y Q18 preguntan por DOC-12 (expirado 2026-08-31) → factor 0.75 lo saca del top3.
# Recall@3 de hibrida_metadata cae a 0.9 por este motivo. La estrategia "hibrida" evita el problema.


# ==========================================
# ETAPA 1: CARGAR DOCUMENTOS
# ==========================================
# Lee cada archivo .md de docs/, separa el bloque "---" de metadata
# (id, tipo, vigencia) del contenido principal.

def leer_documentos():
    docs = []
    for archivo in sorted(DOCS.glob("*.md")):
        texto  = archivo.read_text(encoding="utf-8")
        partes = texto.split("---", 2)
        if len(partes) != 3:
            raise ValueError(f"Formato incorrecto: {archivo.name}")
        meta = {}
        for linea in partes[1].strip().splitlines():
            if ":" in linea:
                c, v = linea.split(":", 1)
                meta[c.strip()] = v.strip().strip('"')
        docs.append({"archivo": archivo.stem, "meta": meta, "contenido": partes[2]})
    return docs


# ==========================================
# ETAPA 2: CHUNKING
# ==========================================
# Divide cada documento en secciones usando "\n# " como delimitador.
# Criterio: un chunk por titulo h1 → fragmentos tematicos coherentes.
# Usa split("\n# ") para que los textos coincidan con el cache
# de embeddings generado previamente.
# Evidencia: 49 chunks de 12 docs, longitud media ~31 tokens.
# Recall@3 = 1.0 sobre las 20 preguntas (ver resultados/evaluacion.json).

def crear_chunks(documentos):
    chunks = []
    for doc in documentos:
        for seccion in doc["contenido"].split("\n# "):
            t = seccion.strip()
            if t:
                chunks.append({
                    "documento":      doc["archivo"],
                    "tipo":           doc["meta"].get("tipo", ""),
                    "vigencia_desde": doc["meta"].get("vigencia_desde", ""),
                    "vigencia_hasta": doc["meta"].get("vigencia_hasta", ""),
                    "texto":          t,
                })
    return chunks


# ==========================================
# ETAPA 3: EMBEDDINGS Y CACHE
# ==========================================
# Genera embeddings via OpenAI API y los guarda en JSON.
# Clave de cache: SHA-256(modelo + texto) — invalida ante cambio de
# modelo o texto. Segunda ejecucion: cero llamadas a la API.

def _clave(texto):
    return hashlib.sha256((MODELO + texto).encode("utf-8")).hexdigest()


def _llamar_api(textos):
    """Llama a la API en un unico batch y devuelve lista de vectores."""
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps({"model": MODELO, "input": textos}).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return [item["embedding"] for item in json.load(r)["data"]]


def cargar_cache_docs(chunks):
    if not CACHE_DOCS.exists():
        raise SystemExit("ERROR: no hay cache de embeddings. Ejecuta buscador.py primero con OPENAI_API_KEY definida.")
    cache = json.loads(CACHE_DOCS.read_text(encoding="utf-8"))
    pendientes = []
    for c in chunks:
        k = _clave(c["texto"])
        if k not in cache:
            pendientes.append((k, c["texto"]))
    if pendientes:
        vectores = _llamar_api([t for _, t in pendientes])
        for (k, _), v in zip(pendientes, vectores):
            cache[k] = v
        CACHE_DOCS.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def cargar_cache_preguntas(preguntas):
    cache = json.loads(CACHE_QS.read_text(encoding="utf-8")) if CACHE_QS.exists() else {}
    pendientes = []
    for p in preguntas:
        k = _clave(p["question"])
        if k not in cache:
            pendientes.append((k, p["question"]))
    nuevos = len(pendientes)
    if pendientes:
        vectores = _llamar_api([t for _, t in pendientes])
        for (k, _), v in zip(pendientes, vectores):
            cache[k] = v
        CACHE_QS.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"Embeddings de preguntas: {nuevos} nuevos, {len(preguntas) - nuevos} del cache")
    return cache


# ==========================================
# ETAPA 4: BUSQUEDA VECTORIAL
# ==========================================
# Similitud coseno implementada con NumPy: mide el angulo entre
# vectores de embedding. Encuentra similitud semantica aunque las
# palabras exactas no coincidan.

def similitud_coseno(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def ranking_vectorial(emb_pregunta):
    resultados = []
    for i, c in enumerate(_chunks):
        k = _clave(c["texto"])
        if k in _cache_docs:
            resultados.append({
                "idx":        i,
                "documento":  c["documento"],
                "puntuacion": similitud_coseno(emb_pregunta, np.array(_cache_docs[k])),
            })
    return sorted(resultados, key=lambda r: r["puntuacion"], reverse=True)


# ==========================================
# ETAPA 5: BUSQUEDA BM25
# ==========================================
# Busqueda lexica desde cero: tokeniza y normaliza (tildes,
# mayusculas), calcula TF por fragmento y IDF suavizado global.
# IDF = log((N - n + 0.5) / (n + 0.5) + 1).
# No requiere API; corre completamente en local.

def tokenizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", texto)


def construir_indice(chunks):
    tok = [tokenizar(c["texto"]) for c in chunks]
    lon = [len(t) for t in tok]
    N   = len(chunks)
    avg = sum(lon) / N if N else 1.0
    df  = {}
    for tokens in tok:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    return {"tok": tok, "lon": lon, "avg": avg, "df": df, "N": N}


def ranking_bm25(pregunta):
    tokens_q = tokenizar(pregunta)
    tok, lon = _indice["tok"], _indice["lon"]
    avg, df, N = _indice["avg"], _indice["df"], _indice["N"]
    resultados = []
    for i, c in enumerate(_chunks):
        tf = {}
        for t in tok[i]:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t in tokens_q:
            if t not in tf:
                continue
            f   = tf[t]
            n   = df.get(t, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1)
            score += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * lon[i] / avg))
        resultados.append({"idx": i, "documento": c["documento"], "puntuacion": score})
    return sorted(resultados, key=lambda r: r["puntuacion"], reverse=True)


# ==========================================
# ETAPA 6: BUSQUEDA HIBRIDA RRF
# ==========================================
# Reciprocal Rank Fusion (k=60): combina rankings por posicion,
# no por puntuacion directa. Cada fragmento acumula 1/(60+pos)
# de cada ranking, haciendo las escalas de coseno y BM25 comparables.

def fusion_rrf(rv, rb):
    scores = {}
    for pos, r in enumerate(rv, 1):
        scores[r["idx"]] = scores.get(r["idx"], 0.0) + 1.0 / (RRF_K + pos)
    for pos, r in enumerate(rb, 1):
        scores[r["idx"]] = scores.get(r["idx"], 0.0) + 1.0 / (RRF_K + pos)
    return scores


# ==========================================
# ETAPA 7: METADATA
# ==========================================
# Determina si un documento esta vigente, expirado o pendiente segun
# su fecha de vigencia y el dia de hoy. Ajusta el puntaje RRF:
# vigente x1.0 | expirado x0.75 | pendiente x0.90.
# Penaliza docs historicos sin eliminarlos: si la pregunta es
# historica, BM25 los seguira posicionando alto de igual manera.

def estado_vigencia(vigencia_desde, vigencia_hasta):
    desde = date.fromisoformat(vigencia_desde)
    hasta = date.fromisoformat(vigencia_hasta) if vigencia_hasta else None
    if HOY < desde:
        return "pendiente"
    if hasta and HOY > hasta:
        return "expirado"
    return "vigente"


def _scores_a_lista(scores, aplicar_vigencia=False):
    resultados = []
    for idx, score in scores.items():
        c      = _chunks[idx]
        estado = estado_vigencia(c["vigencia_desde"], c["vigencia_hasta"])
        factor = FACTOR_VIGENCIA[estado] if aplicar_vigencia else 1.0
        resultados.append({
            "idx":            idx,
            "documento":      c["documento"],
            "tipo":           c["tipo"],
            "estado":         estado,
            "vigencia_desde": c["vigencia_desde"],
            "vigencia_hasta": c["vigencia_hasta"],
            "texto":          c["texto"],
            "puntuacion":     score * factor,
        })
    return sorted(resultados, key=lambda r: r["puntuacion"], reverse=True)


def _enriquecer(lista_minima):
    """Agrega tipo, estado, vigencia y texto a resultados de vectorial/bm25."""
    resultado = []
    for r in lista_minima:
        c = _chunks[r["idx"]]
        resultado.append({
            **r,
            "tipo":           c["tipo"],
            "estado":         estado_vigencia(c["vigencia_desde"], c["vigencia_hasta"]),
            "vigencia_desde": c["vigencia_desde"],
            "vigencia_hasta": c["vigencia_hasta"],
            "texto":          c["texto"],
        })
    return resultado


# ==========================================
# ETAPA 8: BUSCADOR FINAL
# ==========================================
# Funcion principal importable: ejecuta el pipeline completo y
# devuelve los top_k documentos distintos mas relevantes.
# Estrategias: "vectorial" | "bm25" | "hibrida" | "hibrida_metadata"
# Estrategia predeterminada: "hibrida" (RRF, mejor equilibrio medido).

def buscar(pregunta, estrategia="hibrida", top_k=3):
    """
    Busca en los documentos de Zoco Cortex.
    Devuelve lista de hasta top_k dicts:
      {documento, tipo, estado, vigencia_desde, vigencia_hasta,
       texto, puntuacion}
    """
    if estrategia == "bm25":
        lista = _enriquecer(ranking_bm25(pregunta))
    else:
        emb = np.array(_llamar_api([pregunta])[0])
        if estrategia == "vectorial":
            lista = _enriquecer(ranking_vectorial(emb))
        else:
            sc    = fusion_rrf(ranking_vectorial(emb), ranking_bm25(pregunta))
            lista = _scores_a_lista(sc, aplicar_vigencia=(estrategia == "hibrida_metadata"))

    vistos, top = set(), []
    for r in lista:
        if r["documento"] not in vistos:
            vistos.add(r["documento"])
            top.append(r)
        if len(top) == top_k:
            break
    return top


# ==========================================
# ETAPA 9: EVALUACION
# ==========================================
# Evalua las 4 estrategias sobre las 20 preguntas de questions.jsonl.
# Recall@3: fraccion de docs relevantes encontrados en el top 3.
# MRR: promedio de 1/posicion del primer doc relevante encontrado.
# Usa cache de embeddings para las preguntas: segunda ejecucion = 0 API calls.

def recall_at_3(docs, relevantes):
    return round(len(set(docs[:3]) & set(relevantes)) / len(relevantes), 4)


def reciprocal_rank(docs, relevantes):
    for i, d in enumerate(docs, 1):
        if d in set(relevantes):
            return round(1.0 / i, 4)
    return 0.0


def _ranking_docs(lista, k=12):
    vistos, docs = set(), []
    for r in lista:
        if r["documento"] not in vistos:
            vistos.add(r["documento"])
            docs.append(r["documento"])
        if len(docs) == k:
            break
    return docs


def _ejecutar(pregunta, emb, estrategia):
    if estrategia == "vectorial":
        return _enriquecer(ranking_vectorial(emb))
    if estrategia == "bm25":
        return _enriquecer(ranking_bm25(pregunta))
    sc = fusion_rrf(ranking_vectorial(emb), ranking_bm25(pregunta))
    return _scores_a_lista(sc, aplicar_vigencia=(estrategia == "hibrida_metadata"))


def evaluar():
    if not QUESTIONS.exists():
        raise SystemExit(f"ERROR: no se encontro {QUESTIONS}")

    preguntas = []
    with open(QUESTIONS, encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                preguntas.append(json.loads(linea))

    cache_qs    = cargar_cache_preguntas(preguntas)
    estrategias = ["vectorial", "bm25", "hibrida", "hibrida_metadata"]
    acum        = {e: {"recall3": [], "rr": []} for e in estrategias}
    detalle     = []

    for p in preguntas:
        emb  = np.array(cache_qs[_clave(p["question"])])
        fila = {"id": p["id"], "relevantes": p["relevant"]}
        for e in estrategias:
            docs = _ranking_docs(_ejecutar(p["question"], emb, e))
            r3   = recall_at_3(docs, p["relevant"])
            rr   = reciprocal_rank(docs, p["relevant"])
            acum[e]["recall3"].append(r3)
            acum[e]["rr"].append(rr)
            fila[e] = {"top3": docs[:3], "recall3": r3, "rr": rr}
        detalle.append(fila)

    n = len(preguntas)
    resumen = {
        e: {"recall3": round(sum(acum[e]["recall3"]) / n, 4),
            "mrr":     round(sum(acum[e]["rr"])      / n, 4)}
        for e in estrategias
    }

    nombres = {"vectorial": "Vectorial", "bm25": "BM25",
               "hibrida": "Hibrida RRF", "hibrida_metadata": "Hibrida + Metadata"}
    print(f"\n{'ESTRATEGIA':<24} {'RECALL@3':>10} {'MRR':>10}")
    print("-" * 46)
    for e in estrategias:
        print(f"{nombres[e]:<24} {resumen[e]['recall3']:>10.4f} {resumen[e]['mrr']:>10.4f}")
    print("-" * 46)

    print("\nFallos por estrategia (R@3 = 0):")
    for e in estrategias:
        fallos = [f["id"] for f in detalle if f[e]["recall3"] == 0]
        print(f"  {nombres[e]:<24} {fallos if fallos else 'ninguno'}")

    print("\nImpacto de metadata (delta RR vs hibrida base):")
    for f in detalle:
        delta = round(f["hibrida_metadata"]["rr"] - f["hibrida"]["rr"], 4)
        if delta != 0:
            signo = "+" if delta > 0 else ""
            print(f"  {f['id']}  delta={signo}{delta}  relevantes={f['relevantes']}")

    RESULTADOS.parent.mkdir(exist_ok=True)
    RESULTADOS.write_text(
        json.dumps({"fecha": str(HOY), "modelo": MODELO,
                    "resumen": resumen, "preguntas": detalle},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nResultados guardados en: {RESULTADOS}")


# ------------------------------------------------------------------
# INICIALIZACION DEL MODULO
# Se ejecuta una vez al importar o al correr el archivo directamente.
# ------------------------------------------------------------------
if not API_KEY:
    raise SystemExit("ERROR: define la variable de entorno OPENAI_API_KEY")

_chunks    = crear_chunks(leer_documentos())
_cache_docs = cargar_cache_docs(_chunks)
_indice    = construir_indice(_chunks)


# ------------------------------------------------------------------
# PUNTO DE ENTRADA (solo cuando se ejecuta directamente)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if "--evaluar" in sys.argv:
        evaluar()

    else:
        print("Buscador RAG - Zoco Cortex")
        print(f"{len(set(c['documento'] for c in _chunks))} docs | {len(_chunks)} fragmentos")
        print("Estrategia predeterminada: hibrida RRF")
        print("Usa --evaluar para ejecutar las metricas sobre las 20 preguntas.")
        print("Escribe 'salir' para terminar.\n")

        while True:
            pregunta = input("Pregunta: ").strip()
            if not pregunta:
                continue
            if pregunta.lower() in ("salir", "exit", "quit"):
                break
            print()
            for i, r in enumerate(buscar(pregunta), 1):
                print(f"#{i} [{r['documento']}]  {r['tipo']} | {r['estado']}")
                print(r["texto"][:350].strip())
                print()
