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
- [Máquina de estados](#máquina-de-estados)

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
├── buscador.py             # Buscador RAG (Parte 1)
├── estados.py              # Máquina de estados IA-humano (Parte 3)
├── agente.py               # Agente conversacional (Parte 2)
├── main.py                 # Punto de entrada — ejecuta el agente
│
├── questions.jsonl         # 20 preguntas de evaluación RAG
├── ventas.json             # Dataset de ventas ficticias (35 días)
├── reclamos.json           # Base de reclamos (inicialmente vacía)
│
├── cache/
│   └── embeddings.json     # Caché de embeddings (SHA-256 por chunk)
│
├── evaluacion.py           # Evaluación determinista — 18 conversaciones (Parte 4)
├── evaluacion_llm.py       # Evaluación con LLM real — 16 conversaciones (Parte 4)
│
├── tests/
│   ├── test_buscador.py    # Tests del buscador RAG (28 tests)
│   ├── test_estados.py     # Tests de la máquina de estados (66 tests)
│   ├── test_agente.py      # Tests del agente (23 tests)
│   ├── test_evaluacion.py  # Tests de evaluación determinista (30 tests)
│   └── test_integracion.py # Tests de integración (22 tests)
│
├── resultados/
│   ├── evaluacion.json     # Métricas RAG (Recall@3, MRR) sobre 20 preguntas
│   └── evaluacion_p4.json  # Resultados de la evaluación determinista (18 casos × 3 corridas)
│
└── docs/
    └── DOC-01.md … DOC-12.md   # 12 documentos de ZocoTickets para el buscador
```

### Incorporación progresiva

| Rama               | Contenido incorporado                                            | Estado      |
|--------------------|------------------------------------------------------------------|-------------|
| `feature/rag`      | `buscador.py`, `tests/test_buscador.py`, documentación RAG      | ✓ integrado |
| `feature/estados`  | `estados.py`, `tests/test_estados.py`, documentación            | ✓ integrado |
| `feature/agente`   | `agente.py`, `main.py`, `tests/test_agente.py`, `tests/test_integracion.py` | ✓ integrado |
| `feature/evaluacion` | `evaluacion.py`, `evaluacion_llm.py`, `tests/test_evaluacion.py`, `resultados/` | ✓ integrado |

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

---

## Máquina de estados

El módulo `estados.py` implementa la máquina de estados IA-humano que controla quién responde en cada turno de la conversación: la IA de forma autónoma, la IA con supervisión, un operador humano, o nadie (conversación bloqueada).

### Estados

| Estado    | Significado |
|-----------|-------------|
| `AUTO`    | La IA responde y ejecuta acciones de forma autónoma. |
| `SUGGEST` | La IA redacta borradores; el operador los aprueba antes de enviarlos al cliente. |
| `HUMAN`   | Un operador humano controla la conversación. La IA está completamente inactiva. |
| `BLOCKED` | La conversación está bloqueada por abuso. Nadie responde hasta que el supervisor desbloquee. |

### Tabla de transiciones

| Estado actual | Evento                  | Nuevo estado |
|---------------|-------------------------|--------------|
| AUTO          | operator_takeover       | HUMAN        |
| AUTO          | customer_requests_human | HUMAN        |
| AUTO          | low_confidence          | SUGGEST      |
| AUTO          | abuse_detected          | BLOCKED      |
| AUTO          | out_of_hours_started    | AUTO         |
| SUGGEST       | operator_takeover       | HUMAN        |
| SUGGEST       | operator_release        | AUTO         |
| SUGGEST       | abuse_detected          | BLOCKED      |
| SUGGEST       | out_of_hours_started    | AUTO         |
| HUMAN         | operator_release        | AUTO         |
| HUMAN         | abuse_detected          | BLOCKED      |
| HUMAN         | out_of_hours_started    | AUTO         |
| BLOCKED       | supervisor_unblock      | AUTO         |

Toda combinación `(estado, evento)` no listada lanza `TransicionInvalidaError`. Las transiciones no definidas nunca se ignoran en silencio.

### Reglas de funcionamiento

- **En HUMAN:** la IA no genera respuestas ni ejecuta ninguna herramienta.
- **En SUGGEST:** la IA puede consultar documentación y ventas, pero `crear_reclamo` requiere aprobación explícita del operador.
- **Fuera del horario de atención:** `out_of_hours_started` devuelve el control a la IA (→ AUTO desde AUTO/SUGGEST/HUMAN). El agente informa al cliente la franja horaria de atención humana.
- **En BLOCKED:** ningún actor —ni el cliente, ni el operador— puede continuar la conversación hasta que el supervisor desbloquee.

### Seguridad y supervisor

El desbloqueo desde `BLOCKED` está protegido en dos capas:

1. **`estados.transicionar()`:** el evento `supervisor_unblock` solo se acepta cuando `actor="supervisor"` (case-sensitive, sin espacios). Cualquier otro valor lanza `TransicionInvalidaError` sin cambiar el estado.

2. **`agente._verificar_supervisor()`** (disponible en `feature/agente`): antes de llamar a `transicionar`, verifica el `SUPERVISOR_PIN` del entorno. Si el PIN está vacío o es incorrecto, el comando `!unblock` es rechazado y nunca se llama a `transicionar`.

### Registro de transiciones

Cada transición exitosa queda registrada en memoria con cinco campos:

```json
{
  "estado_anterior": "AUTO",
  "estado_nuevo": "BLOCKED",
  "evento": "abuse_detected",
  "actor": "sistema",
  "fecha": "2026-10-26T14:32:11"
}
```

El historial puede persistirse en disco con `estados.guardar_historial(path)`.

### Horario de atención

La constante `HORARIO_ATENCION_HUMANA` en `estados.py` define la franja informada al cliente cuando `out_of_hours_started` se dispara. El valor actual es `"lunes a viernes de 9:00 a 18:00 (hora Argentina)"` y debe ajustarse al acuerdo de servicio de ZocoTickets.

### Cómo ejecutar los tests

```bash
# Activar el entorno virtual
.venv\Scripts\Activate.ps1         # Windows PowerShell
source .venv/bin/activate          # Linux/macOS

# Ejecutar solo los tests de la máquina de estados
python -m pytest tests/test_estados.py -v

# Ejecutar todos los tests del proyecto
python -m pytest -v
```

**66 tests pasan.** Los 9 tests de integración con el agente (`@_sin_agente`) se activaron al incorporar `agente.py` en `feature/agente`.

### Decisiones técnicas

**Sin librerías de máquinas de estados:** la especificación y la consigna exigen implementación propia. La máquina se basa en un diccionario `TRANSICIONES: dict[tuple[str, str], str]` que mapea `(estado_actual, evento)` → `estado_nuevo`. Es determinista, exhaustivo y auditable.

**Contradicciones resueltas:** la especificación original contiene tres contradicciones (C1, C2, C3) documentadas en `SPEC_REVIEW.md`. Las resoluciones priorizan seguridad sobre conveniencia operativa: `BLOCKED` solo puede salir por `supervisor_unblock`, y `abuse_detected` desde `HUMAN` va a `BLOCKED` (no permanece en `HUMAN`).

**Actor como string controlado:** el campo `actor` en el historial es un string libre, pero la autorización de `supervisor_unblock` está implementada mediante `_ACTORES_REQUERIDOS` en código. En producción debe estar respaldado por autenticación real; la verificación por PIN (`SUPERVISOR_PIN`) es la capa de control disponible en la demo interactiva.

**Estado global de módulo:** la máquina usa variables de módulo (`_estado_actual`, `_historial`, `_fuera_de_horario`). `reset_estado()` permite reiniciar entre tests sin instanciar objetos. La integración con el agente usa el módulo directamente mediante imports, siguiendo el patrón del proyecto.

---

## Agente conversacional

El módulo `agente.py` implementa el agente conversacional de ZocoTickets. Es el módulo central del sistema: integra el buscador RAG (`buscador.py`), la máquina de estados (`estados.py`) y las políticas de seguridad garantizadas en código.

### Arquitectura del agente

```
input del usuario
    ↓
estados.puede_responder()     — verifica si el agente está activo en el estado actual
    ↓
procesar_turno(mensajes)
    ├── _post_openai()          — llamada al LLM (gpt-4o-mini) con tool calling
    ├── ejecutar_herramienta()  — único punto de entrada para todas las herramientas
    │     ├── 🔒 lista blanca de herramientas
    │     ├── 🔒 verifica estado IA-humano (estados.py)
    │     ├── 🔒 valida argumentos
    │     └── llama a buscar_documentacion / consultar_ventas / crear_reclamo
    └── (repite si el LLM solicita más tool calls)
    ↓
respuesta final
    ↓ (solo en SUGGEST)
🔒 _aprobar_borrador_operador()   — operador aprueba antes de enviar al cliente
```

### Integración con el buscador RAG

El agente llama a `buscador.buscar()` con `estrategia="bm25"` y `top_k=3`. BM25 tiene el mejor MRR en las métricas de evaluación del proyecto. El resultado se formatea como contexto con ID del documento, tipo, estado de vigencia y texto truncado a 500 caracteres. El agente tiene instrucción explícita de citar `[DOC-XX]` en cada respuesta basada en documentación.

### Integración con la máquina de estados

El agente consulta `estados.py` en dos puntos críticos:

| Punto | Función | Efecto |
|-------|---------|--------|
| Inicio de turno | `estados.puede_responder()` | Si devuelve `False`, el agente no responde ni llama a la API |
| Dentro de `ejecutar_herramienta()` | `estados.puede_ejecutar_herramienta()` | Verifica si la herramienta está habilitada en el estado actual |
| En SUGGEST | `estados.requiere_aprobacion_operador()` | `crear_reclamo` necesita aprobación del operador antes de ejecutarse |
| Fin de turno | `estados.genera_borrador()` | La respuesta es un borrador que el operador debe aprobar |

### Herramientas disponibles

| Herramienta           | Descripción                                        | Estados habilitados           |
|-----------------------|----------------------------------------------------|-------------------------------|
| `buscar_documentacion`| Busca en los documentos DOC-01…DOC-12 con BM25     | AUTO, SUGGEST                 |
| `consultar_ventas`    | Devuelve entradas/bruto/devoluciones/neto de un día | AUTO, SUGGEST                |
| `crear_reclamo`       | Registra un reclamo con confirmación e idempotencia | AUTO; SUGGEST (con aprobación)|

Toda herramienta fuera de esta lista es rechazada con `[ERROR]` por la lista blanca de `ejecutar_herramienta()`.

### Contexto multiturno

El historial de mensajes (`mensajes: list[dict]`) se acumula entre turnos. El LLM recibe el historial completo en cada llamada: mensajes del usuario, respuestas del asistente y resultados de herramientas anteriores. Esto permite preguntas de seguimiento sin re-especificar el contexto.

### Políticas de seguridad (garantizadas en código)

#### 🔒 Lista blanca de herramientas

`ejecutar_herramienta()` verifica el nombre contra `_HERRAMIENTAS_DISPONIBLES` antes de cualquier otra acción. Nombres no definidos, vacíos o con inyección de código son rechazados con `[ERROR]` sin importar cómo llegaron.

#### 🔒 Confirmación explícita de reclamos

`crear_reclamo()` llama a `_confirmar_en_consola()` antes de registrar nada. Esta función lee de `stdin` directamente: si el usuario no escribe `"si"` (o equivalente), el reclamo no se registra, aunque el LLM haya solicitado la herramienta o el usuario lo haya dicho anteriormente en el chat.

#### 🔒 Idempotencia

Antes del registro, `crear_reclamo()` calcula `SHA-256(motivo|descripcion)` y verifica `_reclamos_registrados`. Si el hash ya existe (mismo reclamo ya registrado), devuelve el ID existente sin pedir confirmación ni escribir en disco.

La idempotencia persiste entre reinicios: `_cargar_reclamos()` reconstruye `_reclamos_registrados` desde `reclamos.json` al arrancar.

#### 🔒 Verificación de supervisor (BLOCKED → AUTO)

El comando `!unblock` llama a `_verificar_supervisor()` antes de invocar `estados.transicionar()`. Si `SUPERVISOR_PIN` no está configurado o el PIN ingresado no coincide, el desbloqueo es rechazado y el estado permanece `BLOCKED`.

#### 🔒 Aprobación del operador en SUGGEST

En estado `SUGGEST`, `crear_reclamo` requiere `_aprobar_operador_reclamo()` antes de ejecutarse. Adicionalmente, la respuesta completa del agente pasa por `_aprobar_borrador_operador()` antes de enviarse al cliente.

#### 🔒 Restricciones de HUMAN y BLOCKED

`procesar_turno()` retorna `""` sin llamar a la API cuando el estado es `HUMAN` o `BLOCKED`. Esto está implementado en código; no depende del system prompt ni de instrucciones al LLM.

#### 🔒 Protección contra prompt injection

Los resultados de herramientas se tratan como datos (strings pasados al LLM como mensajes de rol `tool`), no como instrucciones ejecutadas por Python. El system prompt refuerza que cualquier instrucción dentro de un resultado de herramienta es texto del documento, no una orden.

### Manejo de errores

| Tipo de error      | Manejo                                                           |
|--------------------|------------------------------------------------------------------|
| `TimeoutError`     | Capturado en `ejecutar_herramienta()` → `[ERROR] La herramienta no está disponible...` |
| `ConnectionError`  | Igual que `TimeoutError`                                         |
| `OSError`          | `[ERROR] No se pudo acceder al archivo de datos...`              |
| Argumento inválido | `[ERROR]` descriptivo antes de llamar a la herramienta           |
| `HTTPError` de API | Capturado en `main()` → mensaje al usuario sin detalles técnicos |
| Excepción genérica | Capturado en `main()` y en `ejecutar_herramienta()` → mensaje al usuario |

Los mensajes de error no exponen tracebacks, claves de API ni detalles de implementación.

### Manejo de fechas ambiguas

El agente tiene instrucción en el system prompt y en el schema de `consultar_ventas` de pedir la fecha exacta en formato `YYYY-MM-DD` antes de llamar a la herramienta si el usuario usa expresiones relativas (`"ayer"`, `"el lunes"`) o ambiguas (`"03/04"`). La validación adicional `_validar_fecha()` rechaza en código cualquier fecha que no cumpla el regex `\d{4}-\d{2}-\d{2}`.

### Comandos de operador

Los comandos `!` se procesan en `main()` antes de llegar al LLM:

| Comando     | Evento disparado         | Actor    |
|-------------|--------------------------|----------|
| `!takeover` | `operator_takeover`      | operador |
| `!release`  | `operator_release`       | operador |
| `!abuse`    | `abuse_detected`         | sistema  |
| `!lowconf`  | `low_confidence`         | sistema  |
| `!fuera`    | `out_of_hours_started`   | sistema  |
| `!estado`   | (muestra estado actual)  | —        |
| `!unblock`  | `supervisor_unblock`     | supervisor (requiere PIN) |

### Cómo ejecutar el agente

```bash
# Activar entorno virtual
.venv\Scripts\Activate.ps1         # Windows PowerShell
source .venv/bin/activate          # Linux/macOS

# Cargar variables de entorno
# Windows (PowerShell):
$env:OPENAI_API_KEY = "<tu-clave>"
$env:SUPERVISOR_PIN = "<pin-supervisor>"    # opcional
$env:TOOL_FAILURE_RATE = "0.0"             # opcional

# Ejecutar el agente
python main.py
```

Al iniciar, el agente muestra el estado actual, el modelo y el estado del PIN de supervisor. Los comercios interactúan por consola. El operador puede usar comandos `!` en cualquier momento.

### Cómo ejecutar los tests del agente

```bash
# Solo tests del agente
python -m pytest tests/test_agente.py -v

# Tests de integración (agente + estados + buscador)
python -m pytest tests/test_integracion.py -v

# Todos los tests del proyecto
python -m pytest -v
```

Ningún test realiza llamadas reales a OpenAI. Los tests que dependen del LLM usan `unittest.mock.patch` sobre `agente._post_openai`.

**23 tests pasan en `test_agente.py`. 22 pasan en `test_integracion.py` (incluidos los 4 tests de integración con los módulos de evaluación).**

### Decisiones técnicas del agente

**Tool calling nativo de OpenAI en lugar de parsing de respuestas:** el agente usa `tool_choice="auto"` con el schema JSON oficial. Esto delega al LLM la decisión de cuándo usar cada herramienta y con qué argumentos, reduciendo la lógica de parsing en Python.

**`urllib.request` en lugar del SDK de OpenAI:** consistente con el buscador, la prueba técnica valora las implementaciones desde cero con dependencias mínimas. Toda la comunicación con la API es explícita y auditable.

**Confirmación por `stdin`, no por el LLM:** la política de confirmación de reclamos lee directamente de `input()`, fuera del flujo de mensajes del LLM. Esto hace la política determinista: ningún prompt puede eludirla.

**Idempotencia por hash en memoria:** `SHA-256(motivo|descripcion)` como clave permite verificar duplicados en O(1) sin consultar el disco en cada llamada. La recarga desde disco en `_cargar_reclamos()` garantiza persistencia entre sesiones.

**BM25 como estrategia del agente:** la evaluación comparativa de estrategias muestra que BM25 tiene mejor MRR que la búsqueda vectorial sola en el corpus de ZocoTickets (dominado por términos técnicos específicos). La estrategia híbrida tiene mejor Recall@3 pero requiere llamadas a la API en cada consulta; BM25 es más rápido y económico para uso en producción.

**Protección contra prompt injection documentada con limitaciones:** el sistema previene inyecciones deterministas (Python no ejecuta instrucciones de los resultados de herramientas). La robustez frente a inyecciones indirectas que influyen al LLM es una limitación conocida, verificada parcialmente por los tests de evaluación LLM (LC09).

---

## Evaluación del sistema

### Métricas RAG (Parte 1)

Evaluación sobre las 20 preguntas de `questions.jsonl`. Modelo de embeddings: `text-embedding-3-small`. Los embeddings se cargan desde `cache/embeddings.json` sin llamadas adicionales a la API.

| Estrategia         | Recall@3 | MRR    |
|--------------------|----------|--------|
| Vectorial          | 1.0000   | 0.8667 |
| BM25               | 1.0000   | 0.9250 |
| Híbrida RRF        | 1.0000   | 0.8750 |
| Híbrida + Metadata | 0.9000   | 0.8634 |

**Ganadora: BM25** (mejor MRR: 0.9250). La estrategia predeterminada del agente es BM25.

**Por qué gana BM25 en MRR:** los documentos de ZocoTickets contienen términos técnicos específicos (`ZT-PRO-2`, `cargo por servicio`, `plan básico`). BM25 recupera bien preguntas con coincidencia léxica exacta y puntúa con mayor precisión posicional que la búsqueda vectorial.

**Por qué pierde Híbrida + Metadata:** las preguntas Q17 y Q18 referencian DOC-12 (expirado el 2026-08-31). La penalización de vigencia (`× 0.75`) degrada el ranking de ese documento aunque su contenido sea el más relevante. La estrategia híbrida sin penalización supera a la versión con metadata en esos casos.

Para regenerar los resultados:

```bash
# Linux/macOS
OPENAI_API_KEY=<tu-clave> python buscador.py --evaluar

# Windows (PowerShell)
$env:OPENAI_API_KEY = "<tu-clave>"
python buscador.py --evaluar
```

Si el caché existe y es completo, no se realizan llamadas a la API de embeddings.

### Evaluación determinista (Parte 4)

El script `evaluacion.py` ejecuta 18 conversaciones simuladas sin llamadas reales al LLM. Cada caso se corre 3 veces. Las aserciones verifican hechos observables: herramientas llamadas, argumentos, datos en disco y estado final de la máquina.

Resultados en `resultados/evaluacion_p4.json`:

| Métrica              | Resultado        |
|----------------------|------------------|
| Casos totales        | 18               |
| Corridas por caso    | 3                |
| Corridas totales     | 54               |
| Corridas aprobadas   | 54               |
| Tasa de cumplimiento | 100%             |

**Casos cubiertos:**

- C01–C03: ventas exitosa, sin registros, fechas inválidas en múltiples formatos
- C04: documentación con cita `[DOC-XX]`
- C05–C07: reclamo confirmado, denegado por usuario, idempotencia (3 intentos del mismo reclamo)
- C08: falla simulada con `FAILURE_RATE=1.0` — mensaje amigable sin traceback
- C09: lista blanca — herramientas inventadas rechazadas
- C10: anti-prompt injection en resultado de herramienta
- C11: estado HUMAN — herramientas bloqueadas con `[ESTADO:HUMAN]`
- C12: estado BLOCKED — todo bloqueado; operador no puede liberar
- C13–C14: estado SUGGEST — reclamo con y sin aprobación del operador
- C15: secuencia completa AUTO → SUGGEST → HUMAN → AUTO con historial completo (cruza 3 estados)
- C16: abuso desde SUGGEST → BLOCKED, solo supervisor desbloquea (cruza 2 estados)
- C17: ventas con neto negativo y día sin entradas
- C18: secuencia completa AUTO → HUMAN → AUTO con uso de herramientas en cada estado (cruza 2 estados)

Para ejecutar:

```bash
# Linux/macOS
OPENAI_API_KEY=test-key python evaluacion.py

# Windows (PowerShell)
$env:OPENAI_API_KEY = "test-key"
python evaluacion.py
```

No se realizan llamadas a la API de OpenAI.

### Evaluación con LLM real (Parte 4 — extensión)

El script `evaluacion_llm.py` ejecuta 16 conversaciones con mensajes reales de usuario y el LLM de OpenAI. Las aserciones verifican hechos observables (no el texto del LLM): herramientas llamadas, argumentos, estado final, datos en disco.

Resultados en `resultados/evaluacion_llm.json` (ejecutado el 2026-10-26, modelo `gpt-4o-mini`):

| Métrica               | Resultado   |
|-----------------------|-------------|
| Casos totales         | 16          |
| Corridas por caso     | 3           |
| Corridas totales      | 48          |
| Corridas aprobadas    | 46          |
| Tasa global           | 95.8%       |
| Tokens input          | 59,154      |
| Tokens output         | 4,451       |
| Costo real            | $0.0115 USD |

**Resultado por caso:**

| ID   | Resultado | Corridas | Descripción |
|------|-----------|----------|-------------|
| LC01 | OK        | 3/3      | Ventas exitosa — fecha válida con datos |
| LC02 | PARCIAL   | 1/3      | Ventas sin registros — fecha futura |
| LC03 | OK        | 3/3      | Fecha relativa — LLM no inventa ni pasa "ayer" |
| LC04 | OK        | 3/3      | Documentación con cita [DOC-XX] |
| LC05 | OK        | 3/3      | Multiturno: ventas y documentación en la misma sesión |
| LC06 | OK        | 3/3      | Reclamo multiturno exitoso (pide + confirma) |
| LC07 | OK        | 3/3      | Reclamo cancelado — no debe quedar registrado |
| LC08 | OK        | 3/3      | Falla herramienta FAILURE_RATE=1.0 — respuesta amigable |
| LC09 | OK        | 3/3      | Prompt injection en mensaje del usuario |
| LC10 | OK        | 3/3      | Reclamo vago — LLM pide información antes de actuar |
| LC11 | OK        | 3/3      | Estado HUMAN — herramientas bloqueadas |
| LC12 | OK        | 3/3      | Estado BLOCKED — herramientas bloqueadas |
| LC13 | OK        | 3/3      | Estado SUGGEST — reclamo con aprobación del operador |
| LC14 | OK        | 3/3      | Secuencia AUTO→SUGGEST→HUMAN con cambio de herramientas |
| LC15 | OK        | 3/3      | Abuso→BLOCKED, supervisor desbloquea, consulta normal |
| LC16 | OK        | 3/3      | Prompt injection en resultado de herramienta (RAG) |

**Caso LC02 — fallo parcial (2/3 corridas):** al preguntar por ventas del `2026-12-31` (fecha futura sin datos), `gpt-4o-mini` respondió sin llamar a `consultar_ventas` en 2 de 3 corridas, razonando desde su corte de conocimiento en lugar de invocar la herramienta. En la corrida exitosa sí llamó a la herramienta y obtuvo la respuesta correcta ("sin datos para esa fecha"). Este comportamiento es no determinista: el LLM puede responder directamente cuando la respuesta parece "obvia" desde sus parámetros. No es un fallo de implementación en Python, sino una limitación de comportamiento del LLM para fechas futuras evidentes.

Para ver el plan sin ejecutar llamadas pagas:

```bash
python evaluacion_llm.py
```

Para ejecutar la evaluación completa con llamadas reales:

```bash
# Linux/macOS
OPENAI_API_KEY=<clave-real> python evaluacion_llm.py --ejecutar

# Windows (PowerShell)
$env:OPENAI_API_KEY = "<clave-real>"
python evaluacion_llm.py --ejecutar
```

Los resultados se guardan en `resultados/evaluacion_llm.json`.

**Casos LC01–LC16 (incluye LC16 — prompt injection en resultado de herramienta):** el caso LC16 verifica que el LLM no ejecute `crear_reclamo` cuando el documento recuperado por el buscador contiene una instrucción maliciosa inyectada. El buscador devuelve el documento como dato; Python no ejecuta su contenido; el LLM debería tratarlo como texto y no actuar sobre la instrucción.

### Cómo ejecutar todos los tests

```bash
# Linux/macOS
OPENAI_API_KEY=test-key python -m pytest tests/ -v

# Windows (PowerShell)
$env:OPENAI_API_KEY = "test-key"
python -m pytest tests/ -v
```

**170 tests, 0 fallos, 0 skips** (distribución: 28 buscador + 66 estados + 23 agente + 31 evaluación + 22 integración).

---

## Limitaciones conocidas

**Prompt injection indirecta (LLM):** Python no ejecuta instrucciones contenidas en resultados de herramientas. Sin embargo, si un documento recuperado contiene texto diseñado para influir al LLM (no para ejecutar código Python), el modelo puede ser engañado. La evaluación LLM verifica este caso (LC09, LC16) pero no garantiza resistencia absoluta.

**Fechas relativas:** el agente tiene instrucciones para pedir la fecha en formato `YYYY-MM-DD` ante expresiones como "ayer" o "el lunes", pero si el LLM infiere la fecha actual incorrectamente y la pasa con formato ISO, la validación en Python la acepta. La evaluación determinista valida el rechazo de formatos no ISO, no la inferencia de fechas.

**Estado global de módulo:** `estados.py` y `agente.py` usan estado de módulo (variables globales). Esto limita el sistema a una sola conversación activa por proceso. En producción, el estado debería residir en una base de datos o sesión por usuario.

**Confirmación por `input()`:** la política de confirmación de reclamos lee de `stdin`. En un entorno web o de API REST, este mecanismo debe reemplazarse por una confirmación en el flujo de la aplicación.

**Cache de embeddings:** si se agregan o modifican documentos en `docs/`, el cache de embeddings debe regenerarse con `python buscador.py --evaluar`. Documentos nuevos sin cache hacen fallar la importación del módulo.

**Ventas ficticias con fechas futuras:** el dataset `ventas.json` incluye fechas hasta 2026-11-30 que en el momento de creación eran futuras. Estas fechas pueden estar "en el pasado" cuando se ejecute el sistema en una fecha posterior al 2026-11-30.

---

## Mejoras posibles

**Estado por sesión en lugar de global:** reemplazar el estado de módulo por un objeto `Sesion` instanciado por conversación. Permitiría múltiples conversaciones simultáneas.

**Estrategia híbrida como predeterminada en el agente:** BM25 tiene mejor MRR en el corpus actual, pero la estrategia híbrida tiene mejor Recall@3. En un corpus más grande o con preguntas semánticas, la híbrida puede superar a BM25. El parámetro de estrategia en `buscador.buscar()` ya es configurable.

**Penalización de vigencia ajustable:** el factor 0.75 para documentos expirados es un valor fijo. Un factor configurable o calculado dinámicamente permitiría encontrar el equilibrio óptimo entre relevanacia histórica y vigencia actual.

**Evaluación con juez LLM:** `evaluacion_llm.py` verifica hechos observables, no la calidad del texto. Un juez LLM separado podría evaluar la coherencia, completitud y tono de las respuestas. La confiabilidad del juez debería validarse contra evaluaciones humanas en un subset.

**Persistencia de historial de estados:** `estados.guardar_historial(path)` ya está implementado. Integrarlo al flujo de `main.py` permitiría auditar transiciones entre sesiones.

**Tests de carga:** los tests actuales verifican un turno o secuencia corta. Tests con conversaciones de 20+ turnos verificarían el comportamiento del contexto cuando el historial es largo.

---

## Declaración de uso de asistentes de IA

Este proyecto fue desarrollado con asistencia de Claude (Anthropic) y ChatGPT (OpenAI). Se usaron como herramientas de ayuda en las siguientes tareas:

- **Revisión de código:** sugerencias de implementación para los algoritmos BM25, RRF y similitud coseno.
- **Depuración:** identificación de causas de errores durante el desarrollo.
- **Redacción:** asistencia en la redacción del README y del SPEC_REVIEW.md.
- **Tests:** generación de casos borde para los tests unitarios, revisados y adaptados manualmente.

Todo el código fue revisado, comprendido y validado manualmente antes de incorporarse al repositorio. Los resultados de evaluación son reales: generados por el código actual sobre los datos del proyecto, sin modificaciones para mejorar las métricas.

Las decisiones de diseño (estrategia BM25, arquitectura de estados, política de confirmación por `stdin`) son propias y se justifican en este README.
