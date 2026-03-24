import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "fs";
import path from "path";

const BASE_DIR = path.join(process.env.BUSINESS_DIR || "C:\\Users\\Willy\\sistema de egocios");

const server = new McpServer({
  name: "business-machine",
  version: "1.0.0",
});

// ─── Utilidades ──────────────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function today() {
  return new Date().toISOString().split("T")[0];
}

function saveFile(subdir, filename, content) {
  const dir = path.join(BASE_DIR, subdir);
  ensureDir(dir);
  const filepath = path.join(dir, filename);
  fs.writeFileSync(filepath, content, "utf-8");
  return filepath;
}

function readFile(filepath) {
  if (fs.existsSync(filepath)) return fs.readFileSync(filepath, "utf-8");
  return null;
}

function listFiles(subdir, ext = ".md") {
  const dir = path.join(BASE_DIR, subdir);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(ext));
}

// ─── Tool: save_research ─────────────────────────────────────────────────────

server.tool(
  "save_research",
  "Guarda los resultados de investigación de mercado en el sistema",
  {
    topic: z.string().describe("Tema o idea investigada"),
    product_hunt_findings: z.string().describe("Hallazgos de Product Hunt"),
    reddit_voice: z.string().describe("Lenguaje exacto del cliente en Reddit"),
    competitor_gaps: z.string().describe("Gaps encontrados en la competencia"),
    recommendation: z.enum(["construir", "descartar", "investigar_mas"]).describe("Recomendación final"),
  },
  async ({ topic, product_hunt_findings, reddit_voice, competitor_gaps, recommendation }) => {
    const filename = `validacion_${today()}_${topic.replace(/\s+/g, "_").toLowerCase()}.md`;
    const content = `# Investigación: ${topic}
**Fecha:** ${today()}
**Recomendación:** ${recommendation.toUpperCase()}

## Product Hunt — Hallazgos
${product_hunt_findings}

## Voz del Cliente (Reddit)
> Estas son las palabras EXACTAS que usan para describir su frustración.
> Úsalas en el marketing.

${reddit_voice}

## Gaps de la Competencia
${competitor_gaps}

## Conclusión
**Recomendación:** ${recommendation}
`;
    const filepath = saveFile("research", filename, content);
    return {
      content: [
        {
          type: "text",
          text: `✅ Investigación guardada en: research/${filename}\n\nPróximo paso: Si la recomendación es "construir", actualiza PRODUCT_BRIEF.md con esta idea.`,
        },
      ],
    };
  }
);

// ─── Tool: load_transcript ───────────────────────────────────────────────────

server.tool(
  "load_transcript",
  "Carga una transcripción de llamada de ventas desde la carpeta transcripts/",
  {
    client_name: z.string().optional().describe("Nombre del cliente (opcional, para buscar archivo específico)"),
  },
  async ({ client_name }) => {
    const dir = path.join(BASE_DIR, "transcripts");
    if (!fs.existsSync(dir)) {
      return {
        content: [
          {
            type: "text",
            text: "❌ La carpeta 'transcripts/' no existe. Créala y pega la transcripción como archivo .txt o .md",
          },
        ],
      };
    }

    const files = fs.readdirSync(dir).filter((f) => f.endsWith(".txt") || f.endsWith(".md"));

    if (files.length === 0) {
      return {
        content: [
          {
            type: "text",
            text: "❌ No hay transcripciones en la carpeta 'transcripts/'. Pega el archivo .txt con la llamada.",
          },
        ],
      };
    }

    // Buscar por nombre de cliente o tomar el más reciente
    let targetFile = client_name
      ? files.find((f) => f.toLowerCase().includes(client_name.toLowerCase()))
      : files[files.length - 1];

    if (!targetFile) targetFile = files[files.length - 1];

    const content = readFile(path.join(dir, targetFile));
    return {
      content: [
        {
          type: "text",
          text: `📋 Transcripción cargada: ${targetFile}\n\n---\n\n${content}`,
        },
      ],
    };
  }
);

// ─── Tool: save_proposal ─────────────────────────────────────────────────────

server.tool(
  "save_proposal",
  "Guarda una propuesta de ventas generada en el sistema",
  {
    client_name: z.string().describe("Nombre del cliente o empresa"),
    proposal_content: z.string().describe("Contenido completo de la propuesta en markdown"),
    deal_value: z.string().optional().describe("Valor estimado del deal (ej: $5,000)"),
  },
  async ({ client_name, proposal_content, deal_value }) => {
    const slug = client_name.replace(/\s+/g, "_").toLowerCase();
    const filename = `propuesta_${slug}_${today()}.md`;
    const header = deal_value ? `> **Deal potencial:** ${deal_value}\n\n` : "";
    const content = `${header}${proposal_content}`;

    const filepath = saveFile("proposals", filename, content);

    return {
      content: [
        {
          type: "text",
          text: `✅ Propuesta guardada en: proposals/${filename}${deal_value ? `\n💰 Deal potencial: ${deal_value}` : ""}`,
        },
      ],
    };
  }
);

// ─── Tool: save_content ──────────────────────────────────────────────────────

server.tool(
  "save_content",
  "Guarda el contenido de marketing generado por plataforma",
  {
    platform: z.enum(["twitter", "linkedin", "instagram", "newsletter"]).describe("Plataforma de destino"),
    content: z.string().describe("Contenido generado listo para publicar"),
    topic: z.string().describe("Tema del contenido"),
  },
  async ({ platform, content, topic }) => {
    const slug = topic.replace(/\s+/g, "_").toLowerCase().slice(0, 30);
    const filename = `${today()}_${platform}_${slug}.md`;
    const fileContent = `# ${platform.toUpperCase()} — ${topic}
**Fecha:** ${today()}
**Estado:** Pendiente de aprobación

---

${content}
`;
    const filepath = saveFile("content", filename, fileContent);

    return {
      content: [
        {
          type: "text",
          text: `✅ Contenido guardado: content/${filename}\n\n📋 Revisa y aprueba antes de publicar.`,
        },
      ],
    };
  }
);

// ─── Tool: get_product_brief ─────────────────────────────────────────────────

server.tool(
  "get_product_brief",
  "Lee el Product Brief actual del proyecto",
  {},
  async () => {
    const briefPath = path.join(BASE_DIR, "PRODUCT_BRIEF.md");
    const content = readFile(briefPath);

    if (!content) {
      return {
        content: [
          {
            type: "text",
            text: "❌ PRODUCT_BRIEF.md no encontrado. Crea el archivo antes de empezar un sprint.",
          },
        ],
      };
    }

    return {
      content: [{ type: "text", text: content }],
    };
  }
);

// ─── Tool: list_pipeline ─────────────────────────────────────────────────────

server.tool(
  "list_pipeline",
  "Muestra el estado actual del pipeline de negocio: research, proposals, content pendiente",
  {},
  async () => {
    const research = listFiles("research");
    const proposals = listFiles("proposals");
    const content = listFiles("content");
    const transcripts = [
      ...listFiles("transcripts", ".txt"),
      ...listFiles("transcripts", ".md"),
    ];

    const status = `# Estado del Pipeline — ${today()}

## 🔍 Research (${research.length} archivos)
${research.length > 0 ? research.map((f) => `- ${f}`).join("\n") : "- Sin investigaciones guardadas"}

## 📋 Transcripciones de Ventas (${transcripts.length} archivos)
${transcripts.length > 0 ? transcripts.map((f) => `- ${f}`).join("\n") : "- Sin transcripciones. Pega llamadas de ventas en transcripts/"}

## 💰 Propuestas (${proposals.length} archivos)
${proposals.length > 0 ? proposals.map((f) => `- ${f}`).join("\n") : "- Sin propuestas generadas"}

## 📢 Contenido Pendiente (${content.length} archivos)
${content.length > 0 ? content.map((f) => `- ${f}`).join("\n") : "- Sin contenido generado"}
`;

    return {
      content: [{ type: "text", text: status }],
    };
  }
);

// ─── Tool: update_sprint_log ─────────────────────────────────────────────────

server.tool(
  "update_sprint_log",
  "Registra el progreso del sprint actual en el log del proyecto",
  {
    sprint_goal: z.string().describe("Meta del sprint"),
    completed: z.array(z.string()).describe("Lista de tareas completadas"),
    pending: z.array(z.string()).describe("Lista de tareas pendientes"),
    next_sprint: z.string().optional().describe("Sugerencia para el próximo sprint"),
    notes: z.string().optional().describe("Notas adicionales"),
  },
  async ({ sprint_goal, completed, pending, next_sprint, notes }) => {
    const logPath = path.join(BASE_DIR, "SPRINT_LOG.md");
    const existingLog = readFile(logPath) || "# Sprint Log\n\n";

    const entry = `
## Sprint ${today()}
**Meta:** ${sprint_goal}

### ✅ Completado
${completed.map((t) => `- ${t}`).join("\n")}

### 🚧 Pendiente
${pending.length > 0 ? pending.map((t) => `- ${t}`).join("\n") : "- Nada pendiente"}

${next_sprint ? `### 🎯 Próximo Sprint\n${next_sprint}` : ""}
${notes ? `### 📝 Notas\n${notes}` : ""}

---
`;

    fs.writeFileSync(logPath, existingLog + entry, "utf-8");

    return {
      content: [
        {
          type: "text",
          text: `✅ Sprint registrado en SPRINT_LOG.md\n\n**Completado:** ${completed.length} tareas\n**Pendiente:** ${pending.length} tareas`,
        },
      ],
    };
  }
);

// ─── Tool: update_saas_metrics ───────────────────────────────────────────────

server.tool(
  "update_saas_metrics",
  "Actualiza las métricas clave del SaaS en el tracker semanal",
  {
    mrr: z.number().describe("MRR actual en dólares"),
    active_customers: z.number().describe("Número de clientes activos pagando"),
    new_leads: z.number().optional().describe("Leads nuevos esta semana"),
    sales_calls: z.number().optional().describe("Llamadas de ventas realizadas"),
    deals_closed: z.number().optional().describe("Deals cerrados esta semana"),
    churn_rate: z.number().optional().describe("Porcentaje de churn mensual"),
    notes: z.string().optional().describe("Notas de la semana"),
  },
  async ({ mrr, active_customers, new_leads, sales_calls, deals_closed, churn_rate, notes }) => {
    const metricsPath = path.join(BASE_DIR, "SaaS_METRICS.md");
    const existing = readFile(metricsPath) || "";

    const entry = `
## Update — ${today()}
| MRR | Clientes | Leads | Llamadas | Deals | Churn |
|-----|----------|-------|----------|-------|-------|
| $${mrr} | ${active_customers} | ${new_leads ?? "-"} | ${sales_calls ?? "-"} | ${deals_closed ?? "-"} | ${churn_rate !== undefined ? churn_rate + "%" : "-"} |

${notes ? `**Notas:** ${notes}` : ""}
---
`;

    const logPath = path.join(BASE_DIR, "SaaS_METRICS_LOG.md");
    const existingLog = readFile(logPath) || "# Historial de Métricas SaaS\n\n";
    fs.writeFileSync(logPath, existingLog + entry, "utf-8");

    return {
      content: [
        {
          type: "text",
          text: `✅ Métricas actualizadas — ${today()}\n💰 MRR: $${mrr}\n👥 Clientes: ${active_customers}\n\nHistorial guardado en SaaS_METRICS_LOG.md`,
        },
      ],
    };
  }
);

// ─── Tool: add_pipeline_deal ─────────────────────────────────────────────────

server.tool(
  "add_pipeline_deal",
  "Agrega o actualiza un deal en el pipeline de ventas",
  {
    client_name: z.string().describe("Nombre del cliente o empresa"),
    stage: z.enum(["prospecto", "contactado", "llamada_agendada", "propuesta_enviada", "negociacion", "cerrado", "perdido"]),
    deal_value: z.number().describe("Valor del deal en dólares"),
    next_action: z.string().describe("Próxima acción concreta con fecha"),
    notes: z.string().optional().describe("Notas adicionales del deal"),
  },
  async ({ client_name, stage, deal_value, next_action, notes }) => {
    const dir = path.join(BASE_DIR, "proposals");
    ensureDir(dir);
    const pipelinePath = path.join(dir, "PIPELINE.md");
    const existing = readFile(pipelinePath) || "# Pipeline de Ventas\n\n| Cliente | Etapa | Valor | Próxima Acción | Fecha |\n|---------|-------|-------|----------------|-------|\n";

    const stageEmoji = {
      prospecto: "🔵",
      contactado: "📧",
      llamada_agendada: "📞",
      propuesta_enviada: "📄",
      negociacion: "🤝",
      cerrado: "✅",
      perdido: "❌",
    }[stage];

    const line = `| ${stageEmoji} ${client_name} | ${stage} | $${deal_value.toLocaleString()} | ${next_action} | ${today()} |\n`;

    // Append or update
    const updatedContent = existing.includes(client_name)
      ? existing.replace(new RegExp(`.*${client_name}.*\n`), line)
      : existing + line;

    fs.writeFileSync(pipelinePath, updatedContent, "utf-8");

    if (notes) {
      const notePath = path.join(dir, `notes_${client_name.replace(/\s+/g, "_").toLowerCase()}.md`);
      const noteContent = readFile(notePath) || `# Notas: ${client_name}\n\n`;
      fs.writeFileSync(notePath, noteContent + `## ${today()}\n${notes}\n\n`, "utf-8");
    }

    return {
      content: [
        {
          type: "text",
          text: `✅ Pipeline actualizado: ${client_name}\nEtapa: ${stageEmoji} ${stage}\nValor: $${deal_value.toLocaleString()}\nPróximo: ${next_action}`,
        },
      ],
    };
  }
);

// ─── Tool: get_saas_stage ────────────────────────────────────────────────────

server.tool(
  "get_saas_stage",
  "Determina en qué etapa del SaaS Factory está el negocio y qué hacer a continuación",
  {},
  async () => {
    const brief = readFile(path.join(BASE_DIR, "PRODUCT_BRIEF.md")) || "";
    const research = listFiles("research");
    const proposals = listFiles("proposals");
    const metrics = readFile(path.join(BASE_DIR, "SaaS_METRICS_LOG.md")) || "";

    // Detectar etapa basada en evidencia
    let stage = "ETAPA 0 — FÁBRICA DE IDEAS";
    let nextAction = "Ejecuta /research para encontrar tu gap de mercado";

    if (research.length > 0 && brief.includes("buildability") === false) {
      stage = "ETAPA 1 — VALIDACIÓN PRE-CÓDIGO";
      nextAction = "Ejecuta /validate con tu idea top para confirmar que el mercado paga";
    }
    if (proposals.length > 0) {
      stage = "ETAPA 2 — CONCIERGE MVP o ETAPA 3 — BUILD";
      nextAction = "Ejecuta /sprint para construir el MVP. Revisa proposals/ para tus primeros clientes";
    }
    if (metrics.includes("$") && metrics.length > 100) {
      stage = "ETAPA 4 — ESCALADA";
      nextAction = "Enfócate en retención y upsell. Ejecuta /content diariamente para leads orgánicos";
    }

    const status = `# Estado SaaS Factory — ${today()}

## Etapa actual: ${stage}

## Próxima acción
${nextAction}

## Evidencia del sistema
- Investigaciones guardadas: ${research.length}
- Propuestas generadas: ${proposals.length}
- Contenido de marketing: ${listFiles("content").length} piezas
- Transcripciones analizadas: ${listFiles("transcripts", ".txt").length + listFiles("transcripts", ".md").length}

## Para ver el roadmap completo
Ejecuta el comando /saas para ver todas las etapas y sus criterios de éxito.
`;

    return {
      content: [{ type: "text", text: status }],
    };
  }
);

// ─── Start server ─────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
