import asyncio

import httpx
import pytest
import respx

from app.pulp_client import DistributionSummary, PulpClient, build_index_entries
from tests.fake_pulp import fixtures as f


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=f.BASE) as http_client:
        pulp_client = PulpClient(http_client, public_base_url=f.BASE)
        yield pulp_client
        await pulp_client.aclose()


def _paginated(results: list[dict], total: int | None = None) -> dict:
    return {
        "count": len(results) if total is None else total,
        "next": None,
        "previous": None,
        "results": results,
    }


def _summary(name: str, content_type: str) -> DistributionSummary:
    return DistributionSummary(
        pulp_href="href",
        pulp_id="id",
        name=name,
        base_path=name,
        base_url=f"{f.BASE}/{name}/",
        content_type=content_type,
        plugin_name=content_type,
    )


def _mock_pulp(*, remotes: list[dict] | None = None, unconfigured: tuple = ()):
    """Everything list_distribution_rows() reads: the listing, each detail, remotes.

    `unconfigured` names hrefs whose `remote` is blanked, i.e. no upstream at all.
    """
    respx.get(f"{f.BASE}/pulp/api/v3/distributions/").mock(
        return_value=httpx.Response(200, json=_paginated(f.DISTRIBUTIONS_LIST_RESULTS))
    )
    for item in f.DISTRIBUTIONS_LIST_RESULTS:
        href = item["pulp_href"]
        dist = f.DISTRIBUTIONS[href]
        if href in unconfigured:
            dist = {**dist, "remote": None}
        respx.get(href).mock(return_value=httpx.Response(200, json=dist))
    respx.get(f"{f.BASE}/pulp/api/v3/remotes/").mock(
        return_value=httpx.Response(
            200, json=_paginated(f.REMOTES_LIST_RESULTS if remotes is None else remotes)
        )
    )
    respx.head(url__regex=r".*").mock(return_value=httpx.Response(200))


def _pages(*pages: list[dict]):
    """Serve one limit/offset page per call, reporting the combined total."""
    total = sum(len(page) for page in pages)
    return [httpx.Response(200, json=_paginated(page, total)) for page in pages]


@pytest.mark.parametrize(
    "content_type,base_path,expected",
    [
        # The paths the real clients use - see _content_url's comment.
        ("container", "docker", f"{f.BASE}/docker/"),
        ("python", "pypi", f"{f.BASE}/pypi/pypi/simple/"),
        ("npm", "npm", f"{f.BASE}/pulp/content/npm/"),
        ("maven", "maven", f"{f.BASE}/pulp/content/maven/"),
    ],
)
def test_content_url_shape_per_content_type(client, content_type, base_path, expected):
    assert client._content_url(content_type, base_path) == expected


@pytest.mark.asyncio
@respx.mock
async def test_list_distributions_parses_content_type_and_plugin_from_href(client):
    respx.get(f"{f.BASE}/pulp/api/v3/distributions/").mock(
        return_value=httpx.Response(200, json=_paginated(f.DISTRIBUTIONS_LIST_RESULTS))
    )

    distributions = await client.list_distributions()

    by_name = {d.name: d for d in distributions}
    assert by_name["docker"].content_type == "container"
    assert by_name["docker"].plugin_name == "pull-through"
    assert by_name["pypi"].content_type == "python"
    assert by_name["pypi"].plugin_name == "pypi"
    assert by_name["npm"].content_type == "npm"
    assert by_name["maven"].content_type == "maven"


@pytest.mark.asyncio
@respx.mock
async def test_list_distributions_reaches_top_level_entries_behind_container_noise(
    client,
):
    # Regression: distributions are listed newest-first, so the per-image children
    # container pull-through generates come before the handful of top-level
    # distributions created by terraform. Capping how many pages are read hid the
    # last of those (gradle-plugins) from the index entirely.
    noise = [
        {
            "pulp_href": f"{f.BASE}/pulp/api/v3/distributions/container/container/{i:032x}/",
            "name": f"docker/library/image-{i}",
            "base_path": f"docker/library/image-{i}",
        }
        for i in range(1000)
    ]
    respx.get(f"{f.BASE}/pulp/api/v3/distributions/").mock(
        side_effect=_pages(noise, f.DISTRIBUTIONS_LIST_RESULTS)
    )

    distributions = await client.list_distributions()

    assert [d.name for d in distributions] == [
        "docker",
        "pypi",
        "npm",
        "maven",
        "gradle-plugins",
    ]


def test_index_merges_non_oci_distributions_into_one_row_per_content_type():
    # maven, gradle-plugins and sbt-plugins all read the same pool, so a card each
    # would list the same cache three times; OCI registries stay one card each.
    entries = build_index_entries(
        [
            _summary("docker", "container"),
            _summary("quay", "container"),
            _summary("maven", "maven"),
            _summary("pypi", "python"),
            _summary("gradle-plugins", "maven"),
        ]
    )

    assert [(e.name, [d.name for d in e.distributions]) for e in entries] == [
        ("docker", ["docker"]),
        ("quay", ["quay"]),
        ("maven", ["maven", "gradle-plugins"]),
        ("python", ["pypi"]),
    ]
    assert [e.is_oci for e in entries] == [True, True, False, False]
    # maven, gradle-plugins and sbt-plugins all read the same pool, so a row each
    # would list the same cache three times; OCI registries stay one row each.
    # The merged row still has to be findable by the names it swallowed.
    assert "gradle-plugins" in entries[2].search_text


@pytest.mark.asyncio
@respx.mock
async def test_index_counts_cached_items_without_fetching_them(client):
    _mock_pulp()
    children = respx.get(
        f"{f.BASE}/pulp/api/v3/distributions/container/container/"
    ).mock(return_value=httpx.Response(200, json=_paginated(f.CONTAINER_CHILDREN)))
    respx.get(f"{f.BASE}/pulp/api/v3/content/maven/artifact/").mock(
        return_value=httpx.Response(200, json=_paginated(f.MAVEN_ARTIFACTS, total=5967))
    )
    respx.get(f"{f.BASE}/pulp/api/v3/content/python/packages/").mock(
        return_value=httpx.Response(200, json=_paginated([]))
    )
    respx.get(f"{f.BASE}/pulp/api/v3/content/npm/packages/").mock(
        return_value=httpx.Response(200, json=_paginated(f.PYTHON_PACKAGES, total=2840))
    )

    entries = {e.name: e for e in await client.list_index_entries()}

    assert entries["docker"].cached_count == 2
    assert entries["maven"].cached_count == 5967
    assert entries["python"].cached_count == 0
    assert entries["npm"].cached_count == 2840
    # limit=1: the count comes off the envelope, so a 5,967-row pool costs the same
    # as an empty one.
    assert children.calls.last.request.url.params["limit"] == "1"


@pytest.mark.asyncio
@respx.mock
async def test_registry_detail_resolves_child_images(client):
    # One filtered listing of the children, not a GET per href in `distributions`.
    _mock_pulp()
    children_route = respx.get(
        f"{f.BASE}/pulp/api/v3/distributions/container/container/"
    ).mock(return_value=httpx.Response(200, json=_paginated(f.CONTAINER_CHILDREN)))

    detail = await client.get_registry_detail(
        "pull-through", "11111111-1111-1111-1111-111111111111"
    )

    assert {image.name for image in detail.cached_images} == {
        "docker/library/nginx",
        "docker/library/bash",
    }
    assert children_route.calls.last.request.url.params["name__startswith"] == "docker/"


@pytest.mark.asyncio
@respx.mock
async def test_python_content_type_lists_flat_content_pool(client):
    # Python pull-through distributions never get a `repository`, so their content
    # is fetched unfiltered rather than scoped via repository_version.
    _mock_pulp()
    content_route = respx.get(f"{f.BASE}/pulp/api/v3/content/python/packages/").mock(
        return_value=httpx.Response(200, json=_paginated(f.PYTHON_PACKAGES))
    )

    detail = await client.get_content_type_detail("python")

    # Regression: Pulp reports a broken internal pod hostname as this distribution's
    # base_url, so the app must rebuild it from base_path against the configured
    # public base_url. Python's working index path is /pypi/<base_path>/simple/.
    assert detail.distributions[0].summary.base_url == f"{f.BASE}/pypi/pypi/simple/"

    assert detail.empty_reason is None
    assert detail.content_columns == ["Name", "Version", "Filename", "Size", "SHA256"]
    assert [item["Name"] for item in detail.content_items] == ["requests", "httpx"]
    assert "repository_version" not in content_route.calls.last.request.url.params


@pytest.mark.asyncio
@respx.mock
async def test_maven_content_type_merges_its_distributions_over_one_pool(client):
    _mock_pulp()
    artifact_route = respx.get(f"{f.BASE}/pulp/api/v3/content/maven/artifact/").mock(
        return_value=httpx.Response(200, json=_paginated(f.MAVEN_ARTIFACTS))
    )

    detail = await client.get_content_type_detail("maven")

    # Both distributions on one page, and the singular "artifact" endpoint read once
    # rather than once per distribution.
    assert [d.summary.name for d in detail.distributions] == ["maven", "gradle-plugins"]
    # Each maven distribution keeps its own upstream, which the old standalone
    # Remotes page listed detached from the distributions using them.
    assert [d.remote_url for d in detail.distributions] == [
        "https://repo1.maven.org/maven2/",
        "https://plugins.gradle.org/m2/",
    ]
    assert artifact_route.call_count == 1
    assert detail.content_columns == ["Group", "Artifact", "Version", "Filename"]
    assert detail.content_items[0]["Artifact"] == "example-core"


@pytest.mark.asyncio
@respx.mock
async def test_content_type_with_remote_and_empty_pool_is_empty_not_unconfigured(
    client,
):
    # A pull-through distribution is linked to a *remote*, never a repository. An
    # empty content pool must not be reported as "not configured".
    _mock_pulp()
    respx.get(f"{f.BASE}/pulp/api/v3/content/npm/packages/").mock(
        return_value=httpx.Response(200, json=_paginated([]))
    )

    detail = await client.get_content_type_detail("npm")

    assert [d.configured for d in detail.distributions] == [True]
    assert detail.content_items == []
    assert detail.empty_reason == "Cache is empty."


@pytest.mark.asyncio
@respx.mock
async def test_content_type_without_any_remote_is_unconfigured(client):
    _mock_pulp(unconfigured=(f.NPM_HREF,))

    detail = await client.get_content_type_detail("npm")

    assert [d.configured for d in detail.distributions] == [False]
    assert (
        detail.empty_reason
        == "No pull-through cache is configured for this content type."
    )


@pytest.mark.asyncio
@respx.mock
async def test_pagination_walks_offsets_instead_of_following_next_links(client):
    # Pulp builds its `next` links with an http:// scheme, so following them costs a
    # redirect per page - the client asks for offsets against the original URL.
    route = respx.get(f"{f.BASE}/pulp/api/v3/distributions/").mock(
        side_effect=_pages(
            [f.DISTRIBUTIONS_LIST_RESULTS[0]], [f.DISTRIBUTIONS_LIST_RESULTS[1]]
        )
    )

    distributions = await client.list_distributions()

    assert [d.name for d in distributions] == ["docker", "pypi"]
    offsets = [call.request.url.params["offset"] for call in route.calls]
    assert offsets == ["0", "1"]


@pytest.mark.asyncio
@respx.mock
async def test_flat_content_pool_is_capped_but_reports_the_real_total(client):
    # maven's pool holds >23k artifacts live; the page shows a slice and says so.
    _mock_pulp()
    respx.get(f"{f.BASE}/pulp/api/v3/content/maven/artifact/").mock(
        return_value=httpx.Response(
            200, json=_paginated(f.MAVEN_ARTIFACTS * 900, total=23068)
        )
    )

    detail = await client.get_content_type_detail("maven")

    assert len(detail.content_items) == 500
    assert detail.total_items == 23068


@pytest.mark.asyncio
@respx.mock
async def test_list_remotes_filters_out_per_image_container_noise(client):
    respx.get(f"{f.BASE}/pulp/api/v3/remotes/").mock(
        return_value=httpx.Response(200, json=_paginated(f.REMOTES_LIST_RESULTS))
    )

    remotes = await client.list_remotes()

    # The 6 top-level remotes, not the 2 per-image ones in the fixture.
    assert len(remotes) == 6
    assert "https://registry-1.docker.io" in {r.url for r in remotes}


@pytest.mark.asyncio
@respx.mock
async def test_remote_reachability_ok_for_2xx_3xx_4xx(client):
    respx.head("https://example.com/ok").mock(return_value=httpx.Response(200))
    respx.head("https://example.com/redirect").mock(return_value=httpx.Response(302))
    respx.head("https://example.com/not-found").mock(return_value=httpx.Response(404))

    for url in (
        "https://example.com/ok",
        "https://example.com/redirect",
        "https://example.com/not-found",
    ):
        badge = await client._check_remote_reachable(asyncio.Semaphore(1), url)
        assert badge.kind == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_remote_reachability_unreachable_for_5xx_and_connection_error(client):
    respx.head("https://example.com/down").mock(return_value=httpx.Response(503))
    respx.head("https://example.com/timeout").mock(side_effect=httpx.ConnectTimeout)

    for url in ("https://example.com/down", "https://example.com/timeout"):
        badge = await client._check_remote_reachable(asyncio.Semaphore(1), url)
        assert badge.kind == "unreachable"


@pytest.mark.asyncio
@respx.mock
async def test_distribution_rows_pair_each_distribution_with_its_upstream(client):
    _mock_pulp()

    rows = await client.list_distribution_rows()

    assert [(r.summary.name, r.remote_url) for r in rows] == [
        ("docker", "https://registry-1.docker.io"),
        ("pypi", "https://pypi.org/"),
        ("npm", "https://registry.npmjs.org"),
        ("maven", "https://repo1.maven.org/maven2/"),
        ("gradle-plugins", "https://plugins.gradle.org/m2/"),
    ]
    assert all(r.badge.kind == "ok" for r in rows)


@pytest.mark.asyncio
@respx.mock
async def test_distribution_without_a_remote_has_no_badge(client):
    _mock_pulp(unconfigured=(f.NPM_HREF,))

    rows = {r.summary.name: r for r in await client.list_distribution_rows()}

    assert rows["npm"].remote_url is None
    assert rows["npm"].badge is None
    assert rows["npm"].configured is False


@pytest.mark.asyncio
@respx.mock
async def test_distribution_rows_are_cached_and_checked_once_per_upstream(client):
    _mock_pulp()
    reachability = respx.head(url__regex=r".*").mock(return_value=httpx.Response(200))

    results = await asyncio.gather(
        client.list_distribution_rows(), client.list_distribution_rows()
    )

    assert len(results[0]) == 5
    # Two concurrent page loads over 5 distributions with 5 distinct upstreams:
    # one check each, not one per page view.
    assert reachability.call_count == 5


@pytest.mark.asyncio
@respx.mock
async def test_status_counts_pods_not_processes(client):
    # Entries are "<pid>@<pod>" and a pod runs several, so counting entries would
    # report four API pods where Kubernetes runs two.
    respx.get(f"{f.BASE}/pulp/api/v3/status/").mock(
        return_value=httpx.Response(200, json=f.STATUS)
    )

    status = await client.get_status()

    assert [(t.name, len(t.pods), t.processes) for t in status.tiers] == [
        ("API", 2, 4),
        ("Content", 2, 2),
        ("Workers", 1, 1),
    ]
    assert [(v.component, v.version) for v in status.versions] == [
        ("core", "3.116.0"),
        ("container", "2.30.0"),
        ("maven", "0.25.1"),
    ]
    assert status.database_connected and status.redis_connected
    assert status.storage_used == 70901448145
