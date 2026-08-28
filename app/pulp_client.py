"""Async wrapper around the read-only slice of the Pulp 3 API this app needs.

Three quirks of Pulp 3 shape this module:

- Distributions and remotes carry no ``content_type`` field; it has to be parsed
  out of their ``pulp_href``
  (``/pulp/api/v3/{distributions|remotes}/{content_type}/{plugin_name}/{id}/``).
- OCI pull-through auto-creates one child distribution *and* one remote per image
  ever pulled, which swamps both list endpoints. Only the top-level entries
  configured in terraform/provisioning are interesting, so the rest is filtered out.
- Cached content is only scoped per distribution for OCI, where each image gets its
  own child distribution. python/npm/maven content lands in one flat pool per
  content_type instead, so every distribution of a type serves the same packages
  (maven, gradle-plugins and sbt-plugins all read the one maven pool). Hence the two
  shapes below: a registry detail per OCI distribution, and one merged view per
  non-OCI content_type.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

OCI_CONTENT_TYPE = "container"

# content_type -> (flat content-list endpoint, {column: API field}). Endpoint paths
# are not derivable from the content_type (maven's is singular "artifact").
CONTENT_TYPES: dict[str, tuple[str, dict[str, str]]] = {
    "python": (
        "content/python/packages/",
        {
            "Name": "name",
            "Version": "version",
            "Filename": "filename",
            "Size": "size",
            "SHA256": "sha256",
        },
    ),
    "npm": (
        "content/npm/packages/",
        {"Name": "name", "Version": "version", "Path": "relative_path"},
    ),
    "maven": (
        "content/maven/artifact/",
        {
            "Group": "group_id",
            "Artifact": "artifact_id",
            "Version": "version",
            "Filename": "filename",
        },
    ),
}

_PAGE_LIMIT = 1000

# Distributions and cached images are listed in full, but the flat content pools are
# not: maven's holds >23k artifacts, and Pulp serves them at roughly 250 rows per
# second. Neither npm's nor maven's content endpoint supports a substring filter, so
# a slice plus the real total (which the page reports) is as good as this gets.
_MAX_CONTENT_ITEMS = 500

# The index and the row listing both fan out over every distribution, and neither
# changes second-to-second - so each is cached briefly rather than rebuilt per visit.
_CACHE_TTL = 30.0
_REMOTE_STATUS_CONCURRENCY = 5
_REMOTE_STATUS_TIMEOUT = 5.0


@dataclass
class DistributionSummary:
    pulp_href: str
    pulp_id: str
    name: str
    base_path: str
    base_url: str
    content_type: str
    plugin_name: str

    @property
    def is_oci(self) -> bool:
        return self.content_type == OCI_CONTENT_TYPE


@dataclass
class CachedImage:
    name: str
    base_path: str
    registry_path: str


@dataclass
class DistributionRow:
    """A distribution paired with the upstream it pulls through, and its health."""

    summary: DistributionSummary
    remote_url: str | None = None
    # None when there is no remote to check.
    badge: RemoteBadge | None = None

    @property
    def configured(self) -> bool:
        return self.remote_url is not None


@dataclass
class RegistryDetail:
    """One OCI pull-through distribution and the images pulled through it."""

    row: DistributionRow
    cached_images: list[CachedImage]


@dataclass
class ContentTypeDetail:
    """Every distribution of one non-OCI content_type, and their shared pool."""

    content_type: str
    distributions: list[DistributionRow] = field(default_factory=list)
    content_items: list[dict[str, str]] = field(default_factory=list)
    content_columns: list[str] = field(default_factory=list)
    total_items: int = 0
    empty_reason: str | None = None


@dataclass
class IndexEntry:
    """One card on the index: an OCI registry, or a content_type's shared cache."""

    content_type: str
    name: str
    distributions: list[DistributionSummary]
    # How many items are cached behind this row; None when the content type has no
    # known content endpoint.
    cached_count: int | None = None

    @property
    def is_oci(self) -> bool:
        return self.content_type == OCI_CONTENT_TYPE

    @property
    def search_text(self) -> str:
        parts = [self.name, self.content_type]
        for d in self.distributions:
            parts += [d.name, d.base_path, d.base_url]
        return " ".join(parts).lower()


@dataclass
class AppTier:
    """One tier of Pulp processes, folded up by the pod they run on."""

    name: str
    pods: list[str]
    processes: int


@dataclass
class ComponentVersion:
    component: str
    package: str
    version: str


@dataclass
class PulpStatus:
    tiers: list[AppTier] = field(default_factory=list)
    versions: list[ComponentVersion] = field(default_factory=list)
    database_connected: bool = False
    redis_connected: bool = False
    storage_used: int | None = None
    content_origin: str | None = None


@dataclass
class RemoteSummary:
    pulp_href: str
    url: str
    content_type: str


BadgeKind = Literal["ok", "unreachable"]


@dataclass
class RemoteBadge:
    kind: BadgeKind
    label: str
    detail: str | None = None


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pulp_client")


class _TtlCache:
    """One slot, rebuilt at most once per TTL and never concurrently."""

    def __init__(self, ttl: float):
        self._ttl = ttl
        self._value: Any = None
        self._at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, build: Any) -> Any:
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if self._value is None or now - self._at >= self._ttl:
                self._value = await build()
                self._at = now
            return self._value


def _parse_href(href: str) -> tuple[str, str, str]:
    """``.../{kind}/{content_type}/{plugin_name}/{id}/`` -> the last three segments.

    ``pulp_href`` is an absolute URI, so the path is split off first to keep a host
    with its own path segments from shifting the indices.
    """
    path_parts = [p for p in urlsplit(href).path.split("/") if p]
    return path_parts[-3], path_parts[-2], path_parts[-1]


def _is_top_level(content_type: str, plugin_name: str) -> bool:
    """False for the per-image children OCI pull-through generates."""
    return plugin_name == "pull-through" or content_type != OCI_CONTENT_TYPE


def build_index_entries(distributions: list[DistributionSummary]) -> list[IndexEntry]:
    """One card per OCI registry, but one card per non-OCI content_type.

    Non-OCI distributions of a type all serve the same flat pool, so a card each
    would be the same cache listed several times over.
    """
    entries: list[IndexEntry] = []
    groups: dict[str, IndexEntry] = {}
    for dist in distributions:
        if dist.is_oci:
            entries.append(IndexEntry(dist.content_type, dist.name, [dist]))
            continue
        group = groups.get(dist.content_type)
        if group is None:
            group = IndexEntry(dist.content_type, dist.content_type, [])
            groups[dist.content_type] = group
            entries.append(group)
        group.distributions.append(dist)
    return entries


# The tiers /status/ reports, in the order they are shown.
_APP_TIERS = (
    ("API", "online_api_apps"),
    ("Content", "online_content_apps"),
    ("Workers", "online_workers"),
)


def _app_tier(name: str, apps: list[dict[str, Any]]) -> AppTier:
    """Fold `<pid>@<pod>` entries into the pods behind them.

    Each entry is one *process*, and a pod runs several - counting entries would
    report four API pods where Kubernetes runs two.
    """
    return AppTier(
        name=name,
        pods=sorted({app["name"].split("@", 1)[-1] for app in apps}),
        processes=len(apps),
    )


def _api_path(pulp_href: str) -> str:
    """`pulp_href` as a root-relative path, so it goes through the client's base_url."""
    return urlsplit(pulp_href).path


class PulpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        public_base_url: str,
        api_version: str = "v3",
    ):
        self._client = client
        self._api = f"/pulp/api/{api_version}"
        # Content URLs are always rebuilt from base_path rather than read off Pulp's
        # own `base_url` field: python distribution detail responses return an
        # internal pod hostname there instead of the public one.
        self._public_base_url = public_base_url.rstrip("/")
        # Reachability checks hit each remote's upstream URL directly, so they must
        # not carry Pulp's base_url or credentials.
        self._reachability_client = httpx.AsyncClient()
        self._rows_cache = _TtlCache(_CACHE_TTL)
        self._entries_cache = _TtlCache(_CACHE_TTL)

    async def aclose(self) -> None:
        await self._reachability_client.aclose()

    def _content_url(self, content_type: str, base_path: str) -> str:
        # The URL shape genuinely differs per content_type; these are the paths the
        # real clients use (docker pull, pip install, npm, mvn), not just whatever
        # answers a curl. See hack/gen_pull_through_docs.py.
        if content_type == OCI_CONTENT_TYPE:
            return f"{self._public_base_url}/{base_path}/"
        if content_type == "python":
            return f"{self._public_base_url}/pypi/{base_path}/simple/"
        return f"{self._public_base_url}/pulp/content/{base_path}/"

    async def _get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _list(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        max_items: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Collect up to `max_items` results, plus Pulp's reported total.

        Paged by explicit limit/offset rather than by following each page's `next`
        link, because Pulp builds those links with an http:// scheme and every one
        of them costs an extra redirect round-trip.
        """
        items: list[dict[str, Any]] = []
        total = 0
        while max_items is None or len(items) < max_items:
            limit = _PAGE_LIMIT
            if max_items is not None:
                limit = min(limit, max_items - len(items))
            page = await self._get(
                url, {**(params or {}), "limit": limit, "offset": len(items)}
            )
            total = page.get("count", 0)
            results = page.get("results", [])
            items.extend(results)
            if not results or len(items) >= total:
                break
        return items[:max_items], total

    # -- distributions ----------------------------------------------------------

    async def list_distributions(self) -> list[DistributionSummary]:
        items, _ = await self._list(f"{self._api}/distributions/")
        summaries = []
        for item in items:
            content_type, plugin_name, pulp_id = _parse_href(item["pulp_href"])
            # Per-image children are reachable by drilling into their parent's
            # cached-images list, so they don't belong on the index.
            if not _is_top_level(content_type, plugin_name):
                continue
            summaries.append(
                DistributionSummary(
                    pulp_href=item["pulp_href"],
                    pulp_id=pulp_id,
                    name=item["name"],
                    base_path=item["base_path"],
                    base_url=self._content_url(content_type, item["base_path"]),
                    content_type=content_type,
                    plugin_name=plugin_name,
                )
            )
        return summaries

    async def list_index_entries(self) -> list[IndexEntry]:
        return await self._entries_cache.get(self._build_index_entries)

    async def _build_index_entries(self) -> list[IndexEntry]:
        entries = build_index_entries(await self.list_distributions())
        counts = await asyncio.gather(*(self._cached_count(e) for e in entries))
        for entry, count in zip(entries, counts):
            entry.cached_count = count
        return entries

    async def _cached_count(self, entry: IndexEntry) -> int | None:
        """How many items sit behind one index row - asked for as a count, not a page.

        `limit=1` because only the envelope's `count` is wanted; the cost is flat
        (~0.2s) whether the table holds nothing or thousands of rows.
        """
        if entry.is_oci:
            return await self._count(
                f"{self._api}/distributions/{OCI_CONTENT_TYPE}/{OCI_CONTENT_TYPE}/",
                {"name__startswith": f"{entry.distributions[0].base_path}/"},
            )
        content_type = CONTENT_TYPES.get(entry.content_type)
        if content_type is None:
            return None
        return await self._count(f"{self._api}/{content_type[0]}")

    async def _count(self, url: str, params: dict[str, Any] | None = None) -> int:
        page = await self._get(url, {**(params or {}), "limit": 1})
        return page.get("count", 0)

    async def list_distribution_rows(self) -> list[DistributionRow]:
        """Every distribution with its upstream URL and reachability.

        Shared by the two detail pages, and cached whole: it costs a detail GET per
        distribution plus a reachability check per upstream.
        """
        return await self._rows_cache.get(self._build_rows)

    async def _build_rows(self) -> list[DistributionRow]:
        summaries = await self.list_distributions()
        # `remote` is the only field saying whether a distribution has an upstream at
        # all, and the list endpoint doesn't return it - so each distribution needs
        # its own detail GET, fanned out rather than serial.
        details = await asyncio.gather(
            *(self._get(_api_path(s.pulp_href)) for s in summaries)
        )
        remote_urls = {r.pulp_href: r.url for r in await self.list_remotes()}
        urls = [remote_urls.get(d.get("remote") or "") for d in details]

        badges = await self._reachability_badges(urls)
        return [
            DistributionRow(
                summary=summary,
                remote_url=url,
                badge=badges.get(url) if url else None,
            )
            for summary, url in zip(summaries, urls)
        ]

    async def get_registry_detail(
        self, plugin_name: str, pulp_id: str
    ) -> RegistryDetail | None:
        rows = await self.list_distribution_rows()
        row = next(
            (
                r
                for r in rows
                if r.summary.is_oci
                and r.summary.pulp_id == pulp_id
                and r.summary.plugin_name == plugin_name
            ),
            None,
        )
        if row is None:
            return None

        # `dist["distributions"]` only holds hrefs, which would mean one GET per
        # cached image. The list endpoint already returns every field needed and each
        # child is named "<base_path>/<image>", so one filtered listing replaces that
        # fan-out.
        children, _ = await self._list(
            f"{self._api}/distributions/{OCI_CONTENT_TYPE}/{OCI_CONTENT_TYPE}/",
            {"name__startswith": f"{row.summary.base_path}/"},
        )
        return RegistryDetail(
            row=row,
            cached_images=[
                CachedImage(
                    name=child["name"],
                    base_path=child["base_path"],
                    registry_path=child.get("registry_path") or child["base_path"],
                )
                for child in children
            ],
        )

    async def get_content_type_detail(self, content_type: str) -> ContentTypeDetail:
        rows = await self.list_distribution_rows()
        distributions = [r for r in rows if r.summary.content_type == content_type]

        if not any(r.configured for r in distributions):
            return ContentTypeDetail(
                content_type=content_type,
                distributions=distributions,
                empty_reason="No pull-through cache is configured for this content type.",
            )

        if content_type not in CONTENT_TYPES:
            return ContentTypeDetail(
                content_type=content_type,
                distributions=distributions,
                empty_reason=f"Cached content isn't shown for content type '{content_type}' yet.",
            )

        endpoint, fields = CONTENT_TYPES[content_type]
        raw_items, total = await self._list(
            f"{self._api}/{endpoint}", max_items=_MAX_CONTENT_ITEMS
        )
        return ContentTypeDetail(
            content_type=content_type,
            distributions=distributions,
            content_items=[
                {
                    column: str(raw.get(api_field, ""))
                    for column, api_field in fields.items()
                }
                for raw in raw_items
            ],
            content_columns=list(fields),
            total_items=total,
            empty_reason=None if raw_items else "Cache is empty.",
        )

    # -- remotes ----------------------------------------------------------------

    async def list_remotes(self) -> list[RemoteSummary]:
        items, _ = await self._list(f"{self._api}/remotes/")
        summaries = []
        for item in items:
            content_type, plugin_name, _pulp_id = _parse_href(item["pulp_href"])
            if _is_top_level(content_type, plugin_name):
                summaries.append(
                    RemoteSummary(
                        pulp_href=item["pulp_href"],
                        url=item["url"],
                        content_type=content_type,
                    )
                )
        return summaries

    async def _reachability_badges(
        self, urls: list[str | None]
    ) -> dict[str, RemoteBadge]:
        """One check per distinct upstream, run as a bounded fan-out."""
        distinct = sorted({url for url in urls if url})
        semaphore = asyncio.Semaphore(_REMOTE_STATUS_CONCURRENCY)
        badges = await asyncio.gather(
            *(self._check_remote_reachable(semaphore, url) for url in distinct)
        )
        return dict(zip(distinct, badges))

    async def _check_remote_reachable(
        self, semaphore: asyncio.Semaphore, url: str
    ) -> RemoteBadge:
        async with semaphore:
            try:
                response = await self._reachability_client.head(
                    url, timeout=_REMOTE_STATUS_TIMEOUT
                )
                if response.status_code < 500:
                    return RemoteBadge(kind="ok", label="Reachable")
                return RemoteBadge(
                    kind="unreachable",
                    label="Unreachable",
                    detail=f"HTTP {response.status_code}",
                )
            except httpx.HTTPError as exc:
                return RemoteBadge(
                    kind="unreachable", label="Unreachable", detail=str(exc)
                )

    # -- status -----------------------------------------------------------------

    async def get_status(self) -> PulpStatus:
        data = await self._get(f"{self._api}/status/")
        return PulpStatus(
            tiers=[_app_tier(name, data.get(key) or []) for name, key in _APP_TIERS],
            versions=[
                ComponentVersion(
                    component=v.get("component", ""),
                    package=v.get("package", ""),
                    version=v.get("version", ""),
                )
                for v in data.get("versions") or []
            ],
            database_connected=bool(
                (data.get("database_connection") or {}).get("connected")
            ),
            redis_connected=bool((data.get("redis_connection") or {}).get("connected")),
            storage_used=(data.get("storage") or {}).get("used"),
            content_origin=(data.get("content_settings") or {}).get("content_origin"),
        )
