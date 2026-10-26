---
id: DOC-11
titulo: "Soporte y reclamos"
tipo: procedimiento
vigencia_desde: 2026-08-15
vigencia_hasta: 2027-12-31
---

# Categorías
Las categorías de reclamos son PAGO, ENTRADA, LIQUIDACION, ACCESO y OTROS. Cada reclamo debe tener un motivo breve y una descripción entendible.

# Confirmación y unicidad
Antes de registrar un reclamo, el asistente debe mostrar motivo y descripción exactos y pedir confirmación explícita. Una segunda confirmación del mismo reclamo no debe generar un segundo registro.

# Seguimiento
La herramienta crear_reclamo devuelve un identificador, por ejemplo REC-000123. Ese identificador confirma creación del registro, no resolución del inconveniente.

# Manejo de fallas
Ante un timeout, no afirmar que el reclamo se creó sin verificar. No exponer stack traces ni secretos.

# Atención humana
Al pasar a HUMAN el agente deja de responder o ejecutar acciones; en SUGGEST prepara propuestas para un operador que debe aprobarlas.
