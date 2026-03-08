# Sistema de Negocios AI — Una Persona, Operación Completa

> Basado en la metodología de emprendedores de 6-7 cifras que usan Claude Code para el 90% de su operación.

## Setup inicial (una sola vez)

```bash
# Instalar el sistema
scripts\setup.bat
```

---

## Comandos diarios (Slash Commands)

Abre Claude Code en esta carpeta y usa estos comandos:

### `/saas [etapa opcional]`
Pipeline completo de SaaS Factory: de idea a $5K MRR. Muestra en qué etapa estás y qué hacer ahora.
```
/saas           ← te dice en qué etapa estás
/saas etapa 2   ← ejecuta acciones de la etapa 2 (concierge MVP)
```

### `/validate [idea]`
Valida una idea de SaaS ANTES de escribir código. Analiza las 5 preguntas de validación.
```
/validate Dashboard de reportes para agencias de marketing
```

### `/daily`
Arranca el día completo: research matutino, sprint, contenido, y ventas.
```
/daily
```

### `/research [tema opcional]`
Investiga oportunidades de mercado en Product Hunt, Reddit, y competidores.
Guarda los resultados en `research/` con el lenguaje exacto del cliente.
```
/research SaaS para agencias de marketing
/research   ← usa el mercado del Product Brief
```

### `/sprint [meta del día]`
Inicia un sprint de desarrollo. Lee el Product Brief y coordina sub-agentes.
```
/sprint Crear sistema de autenticación con email y Google OAuth
/sprint Conectar Stripe y crear el flujo de pago
```

### `/content [notas del día]`
Transforma tu progreso técnico en contenido para X, LinkedIn e Instagram.
```
/content Hoy conecté la API de OpenAI al dashboard, 3 horas de trabajo
/content   ← te pide las notas interactivamente
```

### `/proposal [nombre del cliente]`
Genera una propuesta de ventas profesional desde una transcripción.
Coloca el archivo de transcripción en `transcripts/` primero.
```
/proposal Juan García
/proposal   ← usa la transcripción más reciente
```

---

## Estructura del sistema

```
sistema de egocios/
├── CLAUDE.md               ← Contexto de operación (Claude lo lee automáticamente)
├── PRODUCT_BRIEF.md        ← Define qué estás construyendo HOY ← EDITA ESTO
├── SPRINT_LOG.md           ← Log automático de sprints (se genera solo)
│
├── .claude/
│   ├── commands/           ← Skills (slash commands)
│   │   ├── research.md     → /research
│   │   ├── sprint.md       → /sprint
│   │   ├── content.md      → /content
│   │   ├── proposal.md     → /proposal
│   │   └── daily.md        → /daily
│   └── settings.json       ← Registra el MCP Server
│
├── mcp-server/             ← Motor del sistema (Node.js)
│   └── index.js            ← Herramientas: save_research, save_proposal, etc.
│
├── transcripts/            ← PON AQUÍ las transcripciones de llamadas (.txt o .md)
├── research/               ← Investigaciones guardadas automáticamente
├── proposals/              ← Propuestas generadas automáticamente
└── content/                ← Contenido de marketing listo para publicar
```

---

## Rutina diaria (del video)

| Bloque | Duración | Comando |
|--------|----------|---------|
| Mañana: Research | 30 min | `/research` |
| Mediodía: Build | 2-4 horas | `/sprint [meta]` |
| Tarde: Contenido | 20 min | `/content [notas]` |
| Noche: Ventas | 15 min | `/proposal [cliente]` |

**Total de gestión activa:** ~1 hora. El resto lo ejecuta Claude.

---

## Flujo de una propuesta de ventas

1. Graba o transcribe tu llamada de ventas
2. Guarda el .txt en `transcripts/nombre_cliente.txt`
3. Ejecuta `/proposal nombre_cliente`
4. Revisa y envía la propuesta desde `proposals/`

---

## MCP Tools disponibles

El servidor MCP expone estas herramientas a Claude:

| Tool | Qué hace |
|------|----------|
| `get_product_brief` | Lee el brief actual del proyecto |
| `save_research` | Guarda investigación de mercado estructurada |
| `load_transcript` | Carga transcripción de llamada de ventas |
| `save_proposal` | Guarda propuesta generada con metadata |
| `save_content` | Guarda contenido de marketing por plataforma |
| `update_sprint_log` | Registra el progreso de cada sprint |
| `list_pipeline` | Muestra estado actual de todo el pipeline |
| `update_saas_metrics` | Actualiza MRR, clientes, churn semanalmente |
| `add_pipeline_deal` | Agrega/actualiza un deal en el pipeline de ventas |
| `get_saas_stage` | Detecta en qué etapa SaaS Factory estás y qué sigue |
