"""Fake Pulp 3 API server for clicking through the real app without live Pulp
credentials.

    uv run uvicorn tests.fake_pulp.server:app --port 9999

The fixtures embed absolute hrefs pointing back here (http://127.0.0.1:9999 by
default; set FAKE_PULP_BASE_URL for another host/port). Then, in another terminal:

    PULP_BASE_URL=http://localhost:9999 PULP_USERNAME=x PULP_PASSWORD=y \\
        uv run uvicorn app.main:app --reload

The reachability checks on the detail pages deliberately hit the real upstream URLs,
not this server. To check the path-prefix deployment, rerun the app with `--root-path /ui`.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tests.fake_pulp import fixtures as f

app = FastAPI(title="Fake Pulp")


def _paginated(results: list[dict]) -> dict:
    return {"count": len(results), "next": None, "previous": None, "results": results}


@app.get("/pulp/api/v3/distributions/")
async def list_distributions():
    return _paginated(f.DISTRIBUTIONS_LIST_RESULTS)


@app.get("/pulp/api/v3/distributions/container/container/")
async def list_container_children(name__startswith: str = ""):
    return _paginated(
        [c for c in f.CONTAINER_CHILDREN if c["name"].startswith(name__startswith)]
    )


@app.get("/pulp/api/v3/distributions/{content_type}/{plugin_name}/{pulp_id}/")
async def distribution_detail(
    content_type: str, plugin_name: str, pulp_id: str, request: Request
):
    href = str(request.url).split("?")[0]
    dist = f.DISTRIBUTIONS.get(href)
    if dist is None:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dist


@app.get("/pulp/api/v3/content/python/packages/")
async def python_packages():
    return _paginated(f.PYTHON_PACKAGES)


@app.get("/pulp/api/v3/content/maven/artifact/")
async def maven_artifacts():
    return _paginated(f.MAVEN_ARTIFACTS)


@app.get("/pulp/api/v3/content/npm/packages/")
async def npm_packages():
    return _paginated([])


@app.get("/pulp/api/v3/remotes/")
async def list_remotes():
    return _paginated(f.REMOTES_LIST_RESULTS)


@app.get("/pulp/api/v3/status/")
async def status():
    return f.STATUS
