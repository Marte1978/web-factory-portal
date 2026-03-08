"""Web Factory Portal — FastAPI Server"""
import asyncio
import json
import uuid
import zipfile
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import portal.state as state
from portal.config import PACKAGES_DIR, BASE_DIR, EXCEL_DEFAULT
from portal.services.excel_loader import load_excel
from portal.services.researcher import research_company

app = FastAPI(title="Web Factory Portal", version="1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── SSE Queue Store ───────────────────────────────────────────────────────────

_queues: dict[str, asyncio.Queue] = {}
_semaphore = asyncio.Semaphore(3)  # max 3 concurrent research jobs


async def emit(job_id: str, event: str, data: dict):
    q = _queues.get(job_id)
    if q:
        await q.put({"event": event, "data": data})


async def sse_generator(job_id: str) -> AsyncGenerator[str, None]:
    q = _queues.get(job_id)
    if not q:
        yield f"event: error\ndata: {json.dumps({'msg': 'Job not found'})}\n\n"
        return
    while True:
        try:
            item = await asyncio.wait_for(q.get(), timeout=120)
            payload = json.dumps(item["data"], ensure_ascii=False)
            yield f"event: {item['event']}\ndata: {payload}\n\n"
            if item["event"] in ("done", "error"):
                break
        except asyncio.TimeoutError:
            yield f"event: ping\ndata: {{}}\n\n"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    # Auto-load default Excel if it exists
    if EXCEL_DEFAULT.exists():
        companies = load_excel(EXCEL_DEFAULT)
        for c in companies:
            cid = state.upsert_company(c)
            # Mark if package already exists
            pkg = PACKAGES_DIR / cid
            if (pkg / "brief.md").exists():
                state.companies[cid]["package_ready"] = True
                state.companies[cid]["researched"] = True
    state.load_from_progress()
    print(f"[Portal] Loaded {len(state.companies)} companies.")


@app.get("/", response_class=HTMLResponse)
async def root():
    html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.post("/api/load-excel")
async def load_excel_file(file: UploadFile = File(None), path: str = None):
    if file:
        dest = BASE_DIR / "uploads" / file.filename
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(await file.read())
        excel_path = dest
    elif path:
        excel_path = Path(path)
    else:
        excel_path = EXCEL_DEFAULT

    if not excel_path.exists():
        raise HTTPException(404, f"File not found: {excel_path}")

    companies = load_excel(excel_path)
    for c in companies:
        cid = state.upsert_company(c)
        pkg = PACKAGES_DIR / cid
        if (pkg / "brief.md").exists():
            state.companies[cid]["package_ready"] = True
            state.companies[cid]["researched"] = True

    return {"loaded": len(companies), "total": len(state.companies)}


@app.get("/api/companies")
async def get_companies(sector: str = None, target: str = None,
                        calidad: str = None, q: str = None,
                        con_paquete: bool = False):
    companies = state.get_all()
    if sector:
        companies = [c for c in companies if sector.lower() in c.get("sector","").lower()]
    if target:
        companies = [c for c in companies if c.get("es_target","") == target.upper()]
    if calidad:
        companies = [c for c in companies if c.get("calidad_web","") == calidad.upper()]
    if q:
        companies = [c for c in companies
                     if q.lower() in c.get("nombre","").lower()
                     or q.lower() in c.get("sector","").lower()]
    if con_paquete:
        companies = [c for c in companies if c.get("package_ready")]
    return companies


@app.get("/api/companies/{cid}")
async def get_company(cid: str):
    c = state.get_by_id(cid)
    if not c:
        raise HTTPException(404)
    return c


@app.get("/api/stats")
async def get_stats():
    all_c = state.get_all()
    pkgs  = [d for d in PACKAGES_DIR.iterdir() if d.is_dir() and (d / "brief.md").exists()]
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
    company = state.get_by_id(cid)
    if not company:
        raise HTTPException(404, f"Company {cid} not found")

    job_id = str(uuid.uuid4())
    _queues[job_id] = asyncio.Queue()
    state.jobs[job_id] = {"company_id": cid, "status": "running"}
    state.active[cid] = job_id

    async def run():
        async with _semaphore:
            try:
                emitter = lambda ev, d: emit(job_id, ev, d)
                result = await research_company(company, emitter)
                state.mark_research_done(cid, result)
                state.companies[cid]["package_ready"] = True
                state.jobs[job_id]["status"] = "done"
            except Exception as e:
                await emit(job_id, "error", {"company_id": cid, "msg": str(e)})
                state.jobs[job_id]["status"] = "error"
            finally:
                state.active.pop(cid, None)

    background_tasks.add_task(run)
    return {"job_id": job_id, "stream_url": f"/api/stream/{job_id}"}


@app.post("/api/research/batch")
async def research_batch(ids: list[str], background_tasks: BackgroundTasks):
    """Research multiple companies sequentially."""
    master_job = str(uuid.uuid4())
    _queues[master_job] = asyncio.Queue()

    async def run_all():
        total = len(ids)
        for i, cid in enumerate(ids, 1):
            company = state.get_by_id(cid)
            if not company or company.get("researched"):
                await emit(master_job, "progress",
                           {"msg": f"Omitiendo {cid} (ya investigada)", "pct": int(i/total*100),
                            "company_id": cid, "step": "skip"})
                continue

            sub_job = str(uuid.uuid4())
            _queues[sub_job] = asyncio.Queue()
            state.active[cid] = sub_job

            async def relay(event, data, _sjid=sub_job, _mjid=master_job):
                data["batch_progress"] = f"{i}/{total}"
                await emit(_mjid, event, data)
                await emit(_sjid, event, data)

            async with _semaphore:
                try:
                    result = await research_company(company, relay)
                    state.mark_research_done(cid, result)
                    state.companies[cid]["package_ready"] = True
                except Exception as e:
                    await emit(master_job, "progress",
                               {"msg": f"Error en {company['nombre']}: {e}",
                                "step": "error", "company_id": cid, "pct": int(i/total*100)})
                finally:
                    state.active.pop(cid, None)
                    _queues.pop(sub_job, None)

        await emit(master_job, "batch_done",
                   {"msg": f"Completado: {total} empresas investigadas", "total": total})

    background_tasks.add_task(run_all)
    return {"job_id": master_job, "stream_url": f"/api/stream/{master_job}", "count": len(ids)}


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    return StreamingResponse(
        sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/packages")
async def list_packages():
    pkgs = []
    for d in PACKAGES_DIR.iterdir():
        if d.is_dir() and (d / "brief.md").exists():
            content_file = d / "content.json"
            meta = {}
            if content_file.exists():
                try:
                    meta = json.loads(content_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            images = list((d / "images").glob("*.png")) + list((d / "images").glob("*.jpg")) if (d / "images").exists() else []
            pkgs.append({
                "slug":        d.name,
                "nombre":      meta.get("company_name", d.name),
                "sector":      meta.get("sector", ""),
                "web_quality": meta.get("web_quality", ""),
                "is_target":   meta.get("is_target", True),
                "has_logo":    (d / "logo.png").exists(),
                "image_count": len(images),
                "has_colors":  (d / "colors.json").exists(),
                "primary_color": meta.get("colors", {}).get("dominant", "#2B5EA7"),
            })
    return sorted(pkgs, key=lambda x: x["nombre"])


@app.get("/api/packages/{slug}")
async def get_package(slug: str):
    pkg_dir = PACKAGES_DIR / slug
    if not pkg_dir.exists():
        raise HTTPException(404)
    brief = (pkg_dir / "brief.md").read_text(encoding="utf-8") if (pkg_dir / "brief.md").exists() else ""
    content = {}
    if (pkg_dir / "content.json").exists():
        content = json.loads((pkg_dir / "content.json").read_text(encoding="utf-8"))
    colors = {}
    if (pkg_dir / "colors.json").exists():
        colors = json.loads((pkg_dir / "colors.json").read_text(encoding="utf-8"))
    images = []
    if (pkg_dir / "images").exists():
        images = [f.name for f in (pkg_dir / "images").iterdir()
                  if f.suffix in (".png", ".jpg", ".jpeg", ".webp")]
    return {
        "slug": slug, "brief": brief, "content": content,
        "colors": colors, "images": images,
        "has_logo": (pkg_dir / "logo.png").exists(),
    }


@app.get("/api/packages/{slug}/download")
async def download_package(slug: str):
    pkg_dir = PACKAGES_DIR / slug
    if not pkg_dir.exists():
        raise HTTPException(404)
    zip_path = PACKAGES_DIR / f"{slug}.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pkg_dir.rglob("*"):
            if f.is_file():
                zf.write(str(f), f.relative_to(pkg_dir))
    return FileResponse(str(zip_path), filename=f"{slug}_brief.zip",
                        media_type="application/zip")


@app.get("/api/packages/{slug}/logo")
async def get_logo(slug: str):
    logo = PACKAGES_DIR / slug / "logo.png"
    if not logo.exists():
        raise HTTPException(404)
    return FileResponse(str(logo), media_type="image/png")


@app.get("/api/packages/{slug}/images/{filename}")
async def get_image(slug: str, filename: str):
    img = PACKAGES_DIR / slug / "images" / filename
    if not img.exists():
        raise HTTPException(404)
    return FileResponse(str(img))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("portal.main:app", host="127.0.0.1", port=8000, reload=True)
