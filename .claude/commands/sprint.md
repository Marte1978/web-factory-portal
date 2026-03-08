Eres un senior engineer coordinando un sprint de desarrollo.

**PASO 1 — Lee el contexto**
Lee `PRODUCT_BRIEF.md` para entender qué estamos construyendo y cuál es la meta de HOY.
Si no existe o está vacío, pide al usuario que lo llene antes de continuar.

**PASO 2 — Planifica el sprint**
Basado en la meta del día, divide el trabajo en tracks paralelos si aplica:
- Track A (Backend): endpoints, lógica de negocio, integraciones
- Track B (Frontend): UI, componentes, routing
- Track C (Infraestructura): DB schema, auth, deployment

Si el sprint es simple (una sola área), trabaja directamente sin dividir.

**PASO 3 — Ejecuta con sub-agentes**
Para cada track, lanza un sub-agente con instrucciones específicas:
- Dale contexto claro: qué construir, con qué tech stack, cómo se conecta con los otros tracks
- Define el output esperado: archivos creados, endpoints listos, componentes funcionando

**PASO 4 — Integración**
Una vez que los sub-agentes terminen, integra todo y verifica que funciona en conjunto.
Reporta qué se completó, qué quedó pendiente, y sugiere la meta del próximo sprint.

**REGLAS:**
- Una sola meta clara por sprint
- No mezcles múltiples features en la misma sesión
- Si hay un blocker, reporta inmediatamente en lugar de adivinar

Meta del sprint: $ARGUMENTS
