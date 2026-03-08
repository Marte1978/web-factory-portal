"""
Web Factory Portal — Cloud Entry Point
Compatible con Render.com, Railway, local.
"""
import asyncio
import json
import os
import uuid
import zipfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Cloud-aware paths
from portal.cloud_config import BASE_DIR, PACKAGES_DIR, DATA_JSON, MAX_CONCURRENT_JOBS

app = FastAPI(title="Web Factory Portal", version="1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── State ─────────────────────────────────────────────────────────────────────
_companies: dict[str, dict] = {}
_queues:    dict[str, asyncio.Queue] = {}
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


def _load_companies():
    if not DATA_JSON.exists():
        return
    with open(DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    for c in data:
        cid = c["id"]
        _companies[cid] = c
        pkg = PACKAGES_DIR / cid
        if (pkg / "brief.md").exists():
            _companies[cid]["package_ready"] = True
            _companies[cid]["researched"]    = True


@app.on_event("startup")
async def startup():
    _load_companies()
    print(f"[Portal] {len(_companies)} companies loaded.")


# ── SSE ───────────────────────────────────────────────────────────────────────
async def emit(job_id: str, event: str, data: dict):
    q = _queues.get(job_id)
    if q:
        await q.put({"event": event, "data": data})


async def sse_gen(job_id: str) -> AsyncGenerator[str, None]:
    q = _queues.get(job_id)
    if not q:
        yield f"event: error\ndata: {json.dumps({'msg':'Job not found'})}\n\n"
        return
    while True:
        try:
            item = await asyncio.wait_for(q.get(), timeout=120)
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
            if item["event"] in ("done", "error", "batch_done"):
                break
        except asyncio.TimeoutError:
            yield "event: ping\ndata: {}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/companies")
async def get_companies(q: str = None, sector: str = None,
                        calidad: str = None, target: str = None,
                        con_paquete: bool = False):
    items = sorted(_companies.values(), key=lambda c: c.get("empleados", 0), reverse=True)
    if q:
        items = [c for c in items if q.lower() in c.get("nombre","").lower()
                 or q.lower() in c.get("sector","").lower()]
    if sector:  items = [c for c in items if c.get("sector","") == sector]
    if calidad: items = [c for c in items if c.get("calidad_web","") == calidad]
    if target:  items = [c for c in items if c.get("es_target","") == target.upper()]
    if con_paquete: items = [c for c in items if c.get("package_ready")]
    return items


@app.get("/api/companies/{cid}")
async def get_company(cid: str):
    c = _companies.get(cid)
    if not c:
        raise HTTPException(404)
    return c


@app.get("/api/stats")
async def stats():
    all_c = list(_companies.values())
    pkgs  = [d for d in PACKAGES_DIR.iterdir()
             if d.is_dir() and (d / "brief.md").exists()] if PACKAGES_DIR.exists() else []
    return {
        "total":          len(all_c),
        "targets":        sum(1 for c in all_c if c.get("es_target") == "SI"),
        "sin_web":        sum(1 for c in all_c if c.get("calidad_web") in ("SIN WEB","CAIDA")),
        "basica":         sum(1 for c in all_c if c.get("calidad_web") == "BASICA"),
        "con_chat_ia":    sum(1 for c in all_c if c.get("chat_ia") == "SI"),
        "researched":     sum(1 for c in all_c if c.get("researched")),
        "packages":       len(pkgs),
        "alta_prioridad": sum(1 for c in all_c if c.get("prioridad") == "ALTA"),
    }


@app.post("/api/research/{cid}")
async def start_research(cid: str, background_tasks: BackgroundTasks):
    company = _companies.get(cid)
    if not company:
        raise HTTPException(404)

    job_id = str(uuid.uuid4())
    _queues[job_id] = asyncio.Queue()

    async def run():
        async with _semaphore:
            try:
                from portal.services.researcher import research_company
                emitter = lambda ev, d: emit(job_id, ev, d)
                result = await research_company(company, emitter)
                _companies[cid].update(result)
                _companies[cid]["package_ready"] = True
            except Exception as e:
                await emit(job_id, "error", {"company_id": cid, "msg": str(e)})

    background_tasks.add_task(run)
    return {"job_id": job_id, "stream_url": f"/api/stream/{job_id}"}


@app.post("/api/research/batch")
async def research_batch(ids: list[str], background_tasks: BackgroundTasks):
    master = str(uuid.uuid4())
    _queues[master] = asyncio.Queue()

    async def run_all():
        from portal.services.researcher import research_company
        total = len(ids)
        for i, cid in enumerate(ids, 1):
            company = _companies.get(cid)
            if not company or company.get("researched"):
                await emit(master, "progress", {
                    "msg": f"Omitiendo: {cid}", "pct": int(i/total*100),
                    "company_id": cid, "step": "skip",
                    "batch_progress": f"{i}/{total}"
                })
                continue

            async def relay(ev, d, _i=i, _t=total):
                d["batch_progress"] = f"{_i}/{_t}"
                await emit(master, ev, d)

            async with _semaphore:
                try:
                    result = await research_company(company, relay)
                    _companies[cid].update(result)
                    _companies[cid]["package_ready"] = True
                except Exception as e:
                    await emit(master, "progress", {
                        "msg": f"Error: {e}", "step": "error",
                        "company_id": cid, "pct": int(i/total*100),
                        "batch_progress": f"{i}/{total}"
                    })

        await emit(master, "batch_done", {"msg": f"Completado: {total} investigadas", "total": total})

    background_tasks.add_task(run_all)
    return {"job_id": master, "stream_url": f"/api/stream/{master}", "count": len(ids)}


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    return StreamingResponse(
        sse_gen(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"}
    )


@app.get("/api/packages")
async def list_packages():
    if not PACKAGES_DIR.exists():
        return []
    pkgs = []
    for d in PACKAGES_DIR.iterdir():
        if d.is_dir() and (d / "brief.md").exists():
            meta = {}
            cf = d / "content.json"
            if cf.exists():
                try: meta = json.loads(cf.read_text(encoding="utf-8"))
                except Exception: pass
            imgs = list((d / "images").glob("*")) if (d / "images").exists() else []
            pkgs.append({
                "slug":          d.name,
                "nombre":        meta.get("company_name", d.name),
                "sector":        meta.get("sector",""),
                "web_quality":   meta.get("web_quality",""),
                "is_target":     meta.get("is_target", True),
                "has_logo":      (d / "logo.png").exists(),
                "image_count":   len(imgs),
                "primary_color": meta.get("colors",{}).get("dominant","#2B5EA7"),
            })
    return sorted(pkgs, key=lambda x: x["nombre"])


@app.get("/api/packages/{slug}")
async def get_package(slug: str):
    d = PACKAGES_DIR / slug
    if not d.exists(): raise HTTPException(404)
    brief   = (d / "brief.md").read_text(encoding="utf-8") if (d / "brief.md").exists() else ""
    content = json.loads((d / "content.json").read_text(encoding="utf-8")) if (d / "content.json").exists() else {}
    colors  = json.loads((d / "colors.json").read_text(encoding="utf-8")) if (d / "colors.json").exists() else {}
    images  = [f.name for f in (d / "images").iterdir()
               if f.suffix.lower() in (".png",".jpg",".jpeg",".webp")] if (d / "images").exists() else []
    return {"slug": slug, "brief": brief, "content": content,
            "colors": colors, "images": images, "has_logo": (d / "logo.png").exists()}


@app.get("/api/packages/{slug}/download")
async def download_package(slug: str):
    d = PACKAGES_DIR / slug
    if not d.exists(): raise HTTPException(404)
    zp = PACKAGES_DIR / f"{slug}.zip"
    with zipfile.ZipFile(str(zp), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in d.rglob("*"):
            if f.is_file(): zf.write(str(f), f.relative_to(d))
    return FileResponse(str(zp), filename=f"{slug}_brief.zip", media_type="application/zip")


@app.get("/api/packages/{slug}/logo")
async def get_logo(slug: str):
    p = PACKAGES_DIR / slug / "logo.png"
    if not p.exists(): raise HTTPException(404)
    return FileResponse(str(p), media_type="image/png")


@app.get("/api/packages/{slug}/images/{filename}")
async def get_image(slug: str, filename: str):
    p = PACKAGES_DIR / slug / "images" / filename
    if not p.exists(): raise HTTPException(404)
    return FileResponse(str(p))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("portal.app:app", host="0.0.0.0", port=port)
