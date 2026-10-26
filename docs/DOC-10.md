---
id: DOC-10
titulo: "Validación QR y acceso"
tipo: operaciones
vigencia_desde: 2026-05-01
vigencia_hasta: 2027-12-31
---

# Control de acceso
Un QR válido se acepta una sola vez por entrada. La app de escaneo debe indicar VALIDA, YA_UTILIZADA, ANULADA o NO_ENCONTRADA.

# Modo offline
En modo offline, el escáner puede validar contra un listado descargado, pero debe sincronizar al recuperar conexión. Si dos dispositivos escanean el mismo QR sin conexión, puede haber un conflicto que debe revisarse en la conciliación de accesos.

# Recomendación operativa
Para eventos de alto aforo se recomienda descargar previamente el listado y probar conexión. La app no debe aceptar manualmente un QR anulado.

# Privacidad
No compartir capturas de QR en canales públicos. El agente no solicita el token completo del código QR.
