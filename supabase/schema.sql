-- Web Factory Portal — Supabase Schema
-- Ejecutar en: Supabase Dashboard > SQL Editor

-- ── Companies ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
  id              TEXT PRIMARY KEY,
  nombre          TEXT NOT NULL,
  sector          TEXT,
  municipio       TEXT,
  empleados       INTEGER,
  telefono        TEXT,
  direccion       TEXT,
  prioridad       TEXT,
  score           FLOAT,
  rnc             TEXT,

  -- Research results
  url             TEXT,
  calidad_web     TEXT,
  score_web       INTEGER,
  chat_ia         TEXT DEFAULT 'NO',
  whatsapp        TEXT DEFAULT 'NO',
  es_target       TEXT DEFAULT 'SI',
  telefonos       TEXT,
  emails          TEXT,

  -- Social media
  facebook        TEXT,
  instagram       TEXT,
  linkedin        TEXT,
  twitter         TEXT,
  youtube         TEXT,
  tiktok          TEXT,
  whatsapp_link   TEXT,

  -- Google Maps
  gmaps_url       TEXT,
  gmaps_rating    FLOAT,
  gmaps_reviews   INTEGER,
  gmaps_hours     TEXT,

  -- Content
  descripcion     TEXT,
  servicios       TEXT,
  titulo_web      TEXT,
  propuesta       TEXT,

  -- Assets
  primary_color   TEXT,
  logo_available  BOOLEAN DEFAULT FALSE,
  photo_count     INTEGER DEFAULT 0,

  -- Status
  researched      BOOLEAN DEFAULT FALSE,
  package_ready   BOOLEAN DEFAULT FALSE,
  research_date   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Research Queue ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_queue (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id   TEXT NOT NULL,
  company_name TEXT NOT NULL,
  status       TEXT DEFAULT 'pending',  -- pending | processing | done | error
  progress_pct INTEGER DEFAULT 0,
  progress_msg TEXT DEFAULT 'En cola...',
  error_msg    TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── RLS Policies ───────────────────────────────────────────────────────────────
ALTER TABLE companies       ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_queue  ENABLE ROW LEVEL SECURITY;

-- Companies: anon can read, service_role can write
CREATE POLICY "companies_read_public"
  ON companies FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "companies_write_service"
  ON companies FOR ALL
  TO service_role
  USING (true);

-- Research queue: anon can read and insert, service_role has full access
CREATE POLICY "queue_read_public"
  ON research_queue FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "queue_insert_public"
  ON research_queue FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "queue_write_service"
  ON research_queue FOR ALL
  TO service_role
  USING (true);

-- ── Realtime ───────────────────────────────────────────────────────────────────
-- Enable realtime on research_queue for live progress updates
ALTER PUBLICATION supabase_realtime ADD TABLE research_queue;
ALTER PUBLICATION supabase_realtime ADD TABLE companies;

-- ── Updated_at trigger ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_updated_at
  BEFORE UPDATE ON companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER queue_updated_at
  BEFORE UPDATE ON research_queue
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Storage bucket (run via Supabase dashboard or API) ─────────────────────────
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('packages', 'packages', true)
-- ON CONFLICT DO NOTHING;
