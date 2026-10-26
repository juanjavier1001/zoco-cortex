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
