"""Static Pulp 3 API response fixtures (shapes taken from pulpcore 3.116.0), shared
by the fake server in server.py and the pulp_client unit tests so the two can't
drift apart.

BASE is overridable via FAKE_PULP_BASE_URL: the fake server is hit by the real app
over a real socket, so the hrefs it hands back must resolve to wherever it listens.
"""

import os
from typing import Any

BASE = os.environ.get("FAKE_PULP_BASE_URL", "http://127.0.0.1:9999")

_DISTS = f"{BASE}/pulp/api/v3/distributions"
_REMOTES = f"{BASE}/pulp/api/v3/remotes"

# -- hrefs --------------------------------------------------------------------------
# Covers an OCI pull-through cache with two pulled-through child images, a python
# cache with content, an empty npm cache, and two maven caches sharing one pool.

DOCKER_HREF = f"{_DISTS}/container/pull-through/11111111-1111-1111-1111-111111111111/"
PYPI_HREF = f"{_DISTS}/python/pypi/22222222-2222-2222-2222-222222222222/"
NPM_HREF = f"{_DISTS}/npm/npm/33333333-3333-3333-3333-333333333333/"
MAVEN_HREF = f"{_DISTS}/maven/maven/44444444-4444-4444-4444-444444444444/"
GRADLE_HREF = f"{_DISTS}/maven/maven/77777777-7777-7777-7777-777777777777/"

NGINX_CHILD_HREF = f"{_DISTS}/container/container/55555555-5555-5555-5555-555555555555/"
BASH_CHILD_HREF = f"{_DISTS}/container/container/66666666-6666-6666-6666-666666666666/"

# Each distribution points at exactly one of these, which is how the UI pairs a
# distribution with its upstream URL.
REMOTE_DOCKER_HREF = (
    f"{_REMOTES}/container/pull-through/aaaa0000-0000-0000-0000-000000000001/"
)
REMOTE_QUAY_HREF = (
    f"{_REMOTES}/container/pull-through/aaaa0000-0000-0000-0000-000000000002/"
)
REMOTE_PYPI_HREF = f"{_REMOTES}/python/python/aaaa0000-0000-0000-0000-000000000003/"
REMOTE_NPM_HREF = f"{_REMOTES}/npm/npm/aaaa0000-0000-0000-0000-000000000004/"
REMOTE_MAVEN_HREF = f"{_REMOTES}/maven/maven/aaaa0000-0000-0000-0000-000000000005/"
REMOTE_GRADLE_HREF = f"{_REMOTES}/maven/maven/aaaa0000-0000-0000-0000-000000000006/"
# Per-image noise: pull-through auto-creates one such remote per image ever pulled.
# On a live instance these outnumber the real ones roughly 30 to 1.
REMOTE_NGINX_IMAGE_HREF = (
    f"{_REMOTES}/container/container/bbbb0000-0000-0000-0000-000000000001/"
)
REMOTE_BASH_IMAGE_HREF = (
    f"{_REMOTES}/container/container/bbbb0000-0000-0000-0000-000000000002/"
)

# -- distributions ------------------------------------------------------------------

DISTRIBUTIONS: dict[str, dict[str, Any]] = {
    DOCKER_HREF: {
        "pulp_href": DOCKER_HREF,
        "name": "docker",
        "base_path": "docker",
        "repository": None,
        "repository_version": None,
        "distributions": [NGINX_CHILD_HREF, BASH_CHILD_HREF],
        "remote": REMOTE_DOCKER_HREF,
        "private": False,
        "description": None,
    },
    PYPI_HREF: {
        "pulp_href": PYPI_HREF,
        "name": "pypi",
        "base_path": "pypi",
        # Python's detail endpoint returns an internal pod hostname here instead of
        # the public one, so pulp_client.py must never read this field.
        "base_url": "https://pulp-api-74c985fdd7-wqvmx/pypi/pypi/",
        # Never populated for pull-through python/npm/maven distributions: their
        # content lands in a flat pool, not a repository.
        "repository": None,
        "repository_version": None,
        "remote": REMOTE_PYPI_HREF,
    },
    NPM_HREF: {
        "pulp_href": NPM_HREF,
        "name": "npm",
        "base_path": "npm",
        "base_url": f"{BASE}/pulp/content/npm/",
        "repository": None,
        "repository_version": None,
        "remote": REMOTE_NPM_HREF,
    },
    MAVEN_HREF: {
        "pulp_href": MAVEN_HREF,
        "name": "maven",
        "base_path": "maven",
        "base_url": f"{BASE}/pulp/content/maven/",
        "repository": None,
        "repository_version": None,
        "remote": REMOTE_MAVEN_HREF,
    },
    GRADLE_HREF: {
        "pulp_href": GRADLE_HREF,
        "name": "gradle-plugins",
        "base_path": "gradle-plugins",
        "base_url": f"{BASE}/pulp/content/gradle-plugins/",
        "repository": None,
        "repository_version": None,
        "remote": REMOTE_GRADLE_HREF,
    },
    NGINX_CHILD_HREF: {
        "pulp_href": NGINX_CHILD_HREF,
        "name": "docker/library/nginx",
        "base_path": "docker/library/nginx",
        "registry_path": "fake-pulp.testing/docker/library/nginx",
        "repository": None,
        "repository_version": None,
        "hidden": False,
        "private": False,
        "remote": None,
        "description": None,
    },
    BASH_CHILD_HREF: {
        "pulp_href": BASH_CHILD_HREF,
        "name": "docker/library/bash",
        "base_path": "docker/library/bash",
        "registry_path": "fake-pulp.testing/docker/library/bash",
        "repository": None,
        "repository_version": None,
        "hidden": False,
        "private": False,
        "remote": None,
        "description": None,
    },
}

# Generic-list-endpoint view of the top-level distributions. The list endpoint omits
# the richer per-type fields - `remote` above all, which is why the UI has to fetch
# each distribution's detail to learn its upstream.
DISTRIBUTIONS_LIST_RESULTS: list[dict[str, Any]] = [
    {
        k: v
        for k, v in DISTRIBUTIONS[href].items()
        if k not in ("remote", "distributions")
    }
    for href in (DOCKER_HREF, PYPI_HREF, NPM_HREF, MAVEN_HREF, GRADLE_HREF)
]

# What /distributions/container/container/?name__startswith=docker/ returns.
CONTAINER_CHILDREN: list[dict[str, Any]] = [
    DISTRIBUTIONS[NGINX_CHILD_HREF],
    DISTRIBUTIONS[BASH_CHILD_HREF],
]

# -- content items ------------------------------------------------------------------

PYTHON_PACKAGES: list[dict[str, Any]] = [
    {
        "pulp_href": f"{BASE}/pulp/api/v3/content/python/packages/b0000000-0000-0000-0000-00000000000{i}/",
        "name": name,
        "version": version,
        "filename": f"{name}-{version}.tar.gz",
        "size": size,
        "sha256": sha,
    }
    for i, (name, version, size, sha) in enumerate(
        [
            ("requests", "2.32.3", 131_942, "a" * 64),
            ("httpx", "0.27.2", 88_120, "b" * 64),
        ],
        start=1,
    )
]

MAVEN_ARTIFACTS: list[dict[str, Any]] = [
    {
        "pulp_href": f"{BASE}/pulp/api/v3/content/maven/artifact/c0000000-0000-0000-0000-000000000001/",
        "group_id": "org.example",
        "artifact_id": "example-core",
        "version": "1.2.3",
        "filename": "example-core-1.2.3.jar",
    }
]

# -- remotes ------------------------------------------------------------------------

REMOTES_LIST_RESULTS: list[dict[str, Any]] = [
    {
        "pulp_href": REMOTE_DOCKER_HREF,
        "name": "docker",
        "url": "https://registry-1.docker.io",
    },
    {"pulp_href": REMOTE_QUAY_HREF, "name": "quay", "url": "https://quay.io"},
    {"pulp_href": REMOTE_PYPI_HREF, "name": "pypi", "url": "https://pypi.org/"},
    {"pulp_href": REMOTE_NPM_HREF, "name": "npm", "url": "https://registry.npmjs.org"},
    {
        "pulp_href": REMOTE_MAVEN_HREF,
        "name": "maven",
        "url": "https://repo1.maven.org/maven2/",
    },
    {
        "pulp_href": REMOTE_GRADLE_HREF,
        "name": "gradle-plugins",
        "url": "https://plugins.gradle.org/m2/",
    },
    # Per-image noise, must be filtered out of list_remotes().
    {
        "pulp_href": REMOTE_NGINX_IMAGE_HREF,
        "name": "docker/library/nginx",
        "url": "https://registry-1.docker.io",
    },
    {
        "pulp_href": REMOTE_BASH_IMAGE_HREF,
        "name": "docker/library/bash",
        "url": "https://registry-1.docker.io",
    },
]

# -- status -------------------------------------------------------------------------
# Two API pods running two processes each, so a test can catch the app counting
# `<pid>@<pod>` entries as pods.

_VERSIONS = {"core": "3.116.0", "container": "2.30.0", "maven": "0.25.1"}

STATUS: dict[str, Any] = {
    "versions": [
        {"component": "core", "version": "3.116.0", "package": "pulpcore"},
        {"component": "container", "version": "2.30.0", "package": "pulp-container"},
        {"component": "maven", "version": "0.25.1", "package": "pulp-maven"},
    ],
    "online_api_apps": [
        {"name": f"{pid}@{pod}", "versions": _VERSIONS}
        for pid, pod in [
            (311381, "pulp-api-65d4859f97-kt2zf"),
            (307682, "pulp-api-65d4859f97-kt2zf"),
            (266760, "pulp-api-65d4859f97-h7p2w"),
            (266761, "pulp-api-65d4859f97-h7p2w"),
        ]
    ],
    "online_content_apps": [
        {"name": f"10@{pod}", "versions": _VERSIONS}
        for pod in ("pulp-content-86c7fc8c67-5nt2r", "pulp-content-86c7fc8c67-7jrdq")
    ],
    "online_workers": [
        {"name": "1@pulp-worker-866b7457d6-hjrdt", "versions": _VERSIONS}
    ],
    "database_connection": {"connected": True},
    "redis_connection": {"connected": True},
    "storage": {"total": None, "used": 70901448145, "free": None},
    "content_settings": {
        "content_origin": BASE,
        "content_path_prefix": "/pulp/content/",
    },
    "domain_enabled": False,
}
