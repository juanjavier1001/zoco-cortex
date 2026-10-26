# Zoco Cortex

Agente conversacional en Python para comercios de ZocoTickets. Responde consultas con información verificable de documentación oficial, consulta ventas simuladas y registra reclamos. Implementa políticas de seguridad garantizadas en código y una máquina de estados para el control IA/operador humano.

Prueba técnica — Pasante de IA, ZOCO Servicios de Pago.

---

## Índice

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Datos y documentos](#datos-y-documentos)
- [Buscador RAG](#buscador-rag)

---

## Requisitos

- Python 3.11 o superior
- Clave de API de OpenAI (para embeddings y LLM)
- Sistema operativo: Linux, macOS o Windows

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd zoco-cortex

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar el entorno virtual
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (Git Bash):
source .venv/Scripts/activate

# 4. Instalar dependencias
pip install -r requirements.txt
```

Las dependencias son `numpy` y `pytest`. Todas las llamadas a la API de OpenAI se realizan con `urllib.request` de la biblioteca estándar; no se usa el SDK oficial `openai`.

---

## Configuración

```bash
cp .env.example .env
```

Editar `.env` con los valores reales:

```env
# Clave de la API de OpenAI (requerida para embeddings y LLM)
OPENAI_API_KEY=<tu-clave-aqui>

# Tasa de fallas simuladas en consultar_ventas y crear_reclamo (0.0 a 1.0)
# 0.0 = sin fallas, 1.0 = falla siempre. Por defecto: 0.0
TOOL_FAILURE_RATE=0.0

# PIN del supervisor para desbloquear conversaciones en estado BLOCKED
# Si no se configura, el comando supervisor_unblock queda deshabilitado
SUPERVISOR_PIN=
```

---

## Estructura del proyecto

Estructura actual del repositorio. Los módulos de código fuente, tests y resultados de evaluación se incorporarán progresivamente en las siguientes ramas.

```
zoco-cortex/
│
├── requirements.txt        # numpy>=1.26, pytest>=9.0
├── .env.example            # Variables de entorno requeridas
├── .gitignore
│
├── README.md
├── SPEC_REVIEW.md          # Revisión crítica de la especificación (Parte 3)
│
├── questions.jsonl         # 20 preguntas de evaluación RAG
├── ventas.json             # Dataset de ventas ficticias (35 días)
├── reclamos.json           # Base de reclamos (inicialmente vacía)
│
└── docs/
    └── DOC-01.md … DOC-12.md   # 12 documentos de ZocoTickets para el buscador
```

### Incorporación progresiva

| Rama               | Contenido que se agrega                                          |
|--------------------|------------------------------------------------------------------|
| `feature/rag`      | `buscador.py`, `tests/test_buscador.py`, documentación RAG      |
| `feature/agente`   | `agente.py`, `main.py`, `tests/test_agente.py`, documentación   |
| `feature/estados`  | `estados.py`, `tests/test_estados.py`, documentación            |
| `feature/evaluacion` | `evaluacion.py`, `evaluacion_llm.py`, tests, resultados, conclusiones |

---

## Datos y documentos

### Documentos del buscador (`docs/`)

12 documentos de ZocoTickets (DOC-01 a DOC-12) que conforman la base de conocimiento del sistema. Cada documento incluye un encabezado con `id`, `tipo`, `vigencia_desde` y `vigencia_hasta`.

### Dataset de ventas (`ventas.json`)

35 días de ventas ficticias de un comercio (2026-09-24 a 2026-11-30). El dataset incluye intencionalmente los casos requeridos por la prueba técnica:

- Un día sin ventas registradas: `2026-10-06` (entradas=0)
- Un día con neto negativo: `2026-10-10` (devoluciones superiores al bruto)
- Al menos una fecha futura respecto de la fecha del sistema: `2026-11-30`

Formato de cada entrada:

```json
"YYYY-MM-DD": {"entradas": N, "bruto": X.XX, "devoluciones": Y.YY, "neto": Z.ZZ}
```

### Dataset de preguntas (`questions.jsonl`)

20 preguntas de evaluación para el buscador RAG (Q01–Q20), cada una con el ID del documento que contiene la respuesta:

```json
{"id": "Q07", "question": "¿Cuál es el mínimo de entradas por mes del plan ZT-PRO-2?", "relevant": ["DOC-07"]}
```

### Base de reclamos (`reclamos.json`)

Inicializada como lista vacía. El agente la carga al iniciar y registra nuevos reclamos durante la ejecución.

### Revisión de especificación (`SPEC_REVIEW.md`)

Documento que lista las contradicciones, ambigüedades y casos faltantes detectados en la especificación de la máquina de estados (Parte 3), con la resolución adoptada para cada uno. Incluye el diagrama de estados en formato Mermaid.

---

## Buscador RAG

El buscador RAG (`buscador.py`) implementa desde cero el pipeline de recuperación de documentos. No utiliza LangChain, LlamaIndex, bases vectoriales, scikit-learn ni ninguna librería de BM25 o retrieval. Las únicas dependencias externas son `numpy` y la API de embeddings de OpenAI.

### Arquitectura general

El módulo expone una función principal `buscar(pregunta, estrategia, top_k)` que devuelve los documentos más relevantes con su metadata y puntuación. Al importarse, el módulo inicializa tres estructuras en memoria: la lista de chunks, el caché de embeddings y el índice BM25.

```
docs/*.md
    ↓ leer_documentos()     — parsea metadata YAML y contenido
    ↓ crear_chunks()        — divide por sección h1
    ↓ cargar_cache_docs()   — embeddings desde cache/embeddings.json
    ↓ construir_indice()    — índice BM25 en memoria
         ↓
      buscar(pregunta)
         ├── ranking_vectorial()   — similitud coseno con embeddings
         ├── ranking_bm25()        — BM25 sobre tokens normalizados
         └── fusion_rrf()          — Reciprocal Rank Fusion (k=60)
```

### Chunking

Cada documento `.md` se divide en secciones usando `"\n# "` como delimitador (encabezados Markdown de nivel 1). Un chunk corresponde a una sección temática coherente.

- 12 documentos → 49 chunks
- Longitud media: ~31 tokens por chunk
- Criterio: mantener fragmentos temáticamente cohesivos; justificado por Recall@3 = 1.0 con la estrategia híbrida (ver `resultados/evaluacion.json` en `feature/evaluacion`)

### Embeddings

Se usa el modelo `text-embedding-3-small` de OpenAI, llamado directamente con `urllib.request` (sin SDK). Los embeddings se guardan en `cache/embeddings.json` con clave SHA-256 del par (modelo, texto). Una segunda ejecución de la evaluación no realiza ninguna llamada a la API.

### Similitud coseno

Implementada manualmente con NumPy:

```
cos(a, b) = (a · b) / (‖a‖ · ‖b‖)
```

```python
def similitud_coseno(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### BM25

Implementado desde cero. El tokenizador normaliza tildes (NFD + filtro de marcas diacríticas) y convierte a minúsculas antes de extraer tokens alfanuméricos. IDF suavizado:

```
IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
```

Parámetros: `K1 = 1.5`, `B = 0.75`.

### Búsqueda híbrida con RRF

Reciprocal Rank Fusion combina los rankings vectorial y BM25 por posición, no por puntuación directa. Esto hace comparables las escalas de coseno y BM25:

```
RRF(d) = Σ_{r ∈ R} 1 / (k + rank_r(d)),   k = 60
```

### Metadata y vigencia

Cada chunk hereda la metadata de su documento (`tipo`, `vigencia_desde`, `vigencia_hasta`). La función `estado_vigencia()` clasifica cada documento como `vigente`, `expirado` o `pendiente` según la fecha del sistema.

La estrategia `hibrida_metadata` aplica un factor de ajuste al puntaje RRF: `vigente × 1.0`, `expirado × 0.75`, `pendiente × 0.90`. La estrategia predeterminada es `hibrida` (sin penalización de vigencia), que evita excluir documentos históricos relevantes.

**Limitación conocida:** el factor 0.75 para documentos expirados perjudica preguntas históricas cuya respuesta está en un documento ya vencido (por ejemplo, Q17 y Q18 sobre DOC-12, expirado el 2026-08-31). Por eso `hibrida` supera a `hibrida_metadata` en esos casos.

### Estrategias disponibles

| Estrategia         | Descripción                                              |
|--------------------|----------------------------------------------------------|
| `vectorial`        | Solo similitud coseno sobre embeddings                   |
| `bm25`             | Solo BM25 léxico, sin llamadas a la API                  |
| `hibrida`          | RRF de vectorial + BM25 (predeterminada)                 |
| `hibrida_metadata` | RRF con penalización por vigencia                        |

### Cómo ejecutar el buscador

```bash
# Activar entorno virtual y cargar variables de entorno
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\Activate.ps1         # Windows PowerShell

# Cargar OPENAI_API_KEY desde .env
export $(grep -v '^#' .env | xargs)   # Linux/macOS
# Windows: set OPENAI_API_KEY=<tu-clave>

# Modo interactivo (estrategia híbrida por defecto)
python buscador.py
```

El buscador usa el caché de embeddings en `cache/embeddings.json`. Si el caché existe y cubre todos los chunks actuales, no realiza ninguna llamada a la API en modo interactivo con BM25.

### Cómo ejecutar los tests del buscador

```bash
# Linux/macOS
OPENAI_API_KEY=test-key python -m pytest tests/test_buscador.py -v

# Windows (PowerShell)
$env:OPENAI_API_KEY = "test-key"
python -m pytest tests/test_buscador.py -v
```

Los tests no realizan llamadas a la API de OpenAI. Los tests de caché verifican que `cargar_cache_docs` no llame a la API cuando el caché está completo; el test de BM25 verifica que `buscar()` con estrategia `bm25` tampoco llame a la API.

**28 tests, 0 fallos.**

### Decisiones técnicas de esta etapa

**Chunking por sección h1:** los documentos de ZocoTickets tienen estructura de secciones Markdown. Dividir por `\n# ` produce fragmentos cohesivos de tamaño razonable (~31 tokens) sin fragmentar información relacionada. Se verificó que produce Recall@3 = 1.0 con la estrategia híbrida.

**Caché con SHA-256(modelo + texto):** la clave incluye el modelo para que un cambio de modelo invalide el caché automáticamente, evitando comparar embeddings de modelos distintos.

**RRF en lugar de suma de scores:** las escalas de coseno (−1 a 1) y BM25 (0 a ∞) no son directamente sumables. RRF usa solo las posiciones, haciendo la fusión agnóstica a las magnitudes de cada método.

**Estrategia predeterminada `hibrida`:** la combinación vectorial + BM25 sin penalización de vigencia obtiene el mejor balance entre precisión semántica y coincidencia léxica, y evita excluir documentos históricos válidos.

**urllib.request en lugar del SDK de OpenAI:** la prueba técnica prohíbe el uso de librerías de retrieval y valora las implementaciones desde cero. Usar la biblioteca estándar para las llamadas HTTP mantiene las dependencias mínimas (`numpy` y `pytest`) y hace explícito el contrato de la API.
