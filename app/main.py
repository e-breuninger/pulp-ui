import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.pulp_client import OCI_CONTENT_TYPE, PulpClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pulp_ui")

APP_DIR = Path(__file__).resolve().parent


def template_directories(custom_dir: Path | None) -> list[Path]:
    """Search path for templates, most specific first.

    A file in custom_dir shadows the bundled one of the same name, which is how
    a deployment swaps in its own footer.html without forking the templates.
    """
    dirs = [APP_DIR / "templates"]
    if custom_dir is not None:
        if custom_dir.is_dir():
            dirs.insert(0, custom_dir)
        else:
            logger.warning(
                "PULP_UI_CUSTOM_DIR %s does not exist; ignoring.", custom_dir
            )
    return dirs


CUSTOM_STATIC_DIR = (
    settings.custom_dir / "static" if settings.custom_dir is not None else None
)
HAS_CUSTOM_STATIC = CUSTOM_STATIC_DIR is not None and CUSTOM_STATIC_DIR.is_dir()
HAS_CUSTOM_CSS = HAS_CUSTOM_STATIC and (CUSTOM_STATIC_DIR / "custom.css").is_file()


def branding(request: Request) -> dict:
    """Makes the branding overrides available to base.html without every route
    passing them along."""
    extra_css_url = settings.extra_css_url
    # Built through url_for rather than hardcoded, so it survives --root-path.
    if extra_css_url is None and HAS_CUSTOM_CSS:
        extra_css_url = str(request.url_for("custom_static", path="custom.css"))
    return {"logo_url": settings.logo_url, "extra_css_url": extra_css_url}


templates = Jinja2Templates(
    directory=template_directories(settings.custom_dir),
    context_processors=[branding],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        base_url=settings.base_url,
        auth=(settings.pulp_username, settings.pulp_password),
        timeout=30.0,
        # Pulp's gateway redirects HTTP to HTTPS; without this every request 500s
        # unless PULP_BASE_URL is already the exact https:// origin. httpx keeps
        # Authorization across same-host http->https redirects, so it's safe.
        follow_redirects=True,
    ) as client:
        pulp_client = PulpClient(
            client,
            public_base_url=settings.base_url,
            api_version=settings.pulp_api_version,
        )
        app.state.pulp_client = pulp_client
        try:
            yield
        finally:
            await pulp_client.aclose()


app = FastAPI(title="Pulp UI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# Assets for custom templates (a logo, a stylesheet). Only mounted when present,
# so the default deployment doesn't advertise an empty route.
if HAS_CUSTOM_STATIC:
    app.mount(
        "/custom-static",
        StaticFiles(directory=str(CUSTOM_STATIC_DIR)),
        name="custom_static",
    )


@app.exception_handler(httpx.HTTPError)
async def _pulp_unreachable(request: Request, exc: httpx.HTTPError):
    # Otherwise an unreachable Pulp surfaces as an unhandled 500 traceback.
    logger.error("Pulp API request failed for %s: %s", request.url, exc)
    return HTMLResponse(
        "Pulp API is unreachable or timed out. Try again shortly.", status_code=502
    )


def _pulp_client(request: Request) -> PulpClient:
    return request.app.state.pulp_client


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    entries = await _pulp_client(request).list_index_entries()
    return templates.TemplateResponse(request, "index.html", {"entries": entries})


@app.get(
    "/registries/{plugin_name}/{pulp_id}",
    response_class=HTMLResponse,
)
async def registry_detail(request: Request, plugin_name: str, pulp_id: str):
    detail = await _pulp_client(request).get_registry_detail(plugin_name, pulp_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="No such registry.")
    return templates.TemplateResponse(request, "registry.html", {"detail": detail})


@app.get("/content/{content_type}", response_class=HTMLResponse)
async def content_type_detail(request: Request, content_type: str):
    detail = await _pulp_client(request).get_content_type_detail(content_type)
    return templates.TemplateResponse(request, "content_type.html", {"detail": detail})


@app.get("/distributions/{content_type}/{plugin_name}/{pulp_id}")
async def legacy_distribution_detail(
    request: Request, content_type: str, plugin_name: str, pulp_id: str
):
    # The per-distribution page only survives for OCI; every other content_type now
    # has one merged page. Kept so older links still land somewhere useful.
    if content_type == OCI_CONTENT_TYPE:
        url = request.url_for(
            "registry_detail", plugin_name=plugin_name, pulp_id=pulp_id
        )
    else:
        url = request.url_for("content_type_detail", content_type=content_type)
    return RedirectResponse(url, status_code=301)


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    return templates.TemplateResponse(
        request, "status.html", {"status": await _pulp_client(request).get_status()}
    )
