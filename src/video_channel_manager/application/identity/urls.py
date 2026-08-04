from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from video_channel_manager.application.identity.digest import evidence_digest
from video_channel_manager.application.identity.models import CanonicalUrlEvidence, UrlRouteKind


_RULESET_VERSION = "wave-8b-v1"
_SIMPLE_TRAILING_URL_PUNCTUATION = ".,;:!?»”'\""
_BRACKET_PAIRS = (("(", ")"), ("[", "]"), ("{", "}"))
_ADMIN_HOSTS = frozenset({"studio.youtube.com"})
_ADMIN_PATH_SEGMENTS = frozenset({"admin", "manage", "manager", "edit", "studio", "settings", "creator"})
_ADMIN_QUERY_VALUES = frozenset({"admin", "edit", "manage", "manager", "settings", "studio"})


def _strip_trailing_url_punctuation(value: str) -> str:
    result = value.strip().rstrip(_SIMPLE_TRAILING_URL_PUNCTUATION)
    changed = True
    while result and changed:
        changed = False
        for opening, closing in _BRACKET_PAIRS:
            if result.endswith(closing) and result.count(closing) > result.count(opening):
                result = result[:-1].rstrip(_SIMPLE_TRAILING_URL_PUNCTUATION)
                changed = True
    return result


def _canonical_url_parts(value: str) -> tuple[str, list[str]]:
    transformations: list[str] = []
    raw = _strip_trailing_url_punctuation(value)
    if raw != value:
        transformations.append("strip_outer_or_trailing_punctuation")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid HTTP(S) URL: {value}")
    if parsed.username or parsed.password:
        raise ValueError("Credentials are not allowed in editorial URLs.")

    scheme = parsed.scheme.lower()
    original_scheme = raw.split(":", 1)[0]
    if original_scheme != scheme:
        transformations.append("lowercase_scheme")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError(f"Invalid URL host: {value}")
    original_netloc = parsed.netloc.rsplit("@", 1)[-1]
    if original_netloc.startswith("["):
        closing = original_netloc.find("]")
        original_hostname = original_netloc[1:closing] if closing >= 0 else original_netloc
    else:
        host_candidate, separator, port_candidate = original_netloc.rpartition(":")
        original_hostname = host_candidate if separator and port_candidate.isdigit() else original_netloc
    if original_hostname != hostname:
        transformations.append("lowercase_host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid URL port: {value}") from exc
    if port is None or (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        netloc = hostname
        if port is not None:
            transformations.append("remove_default_port")
    else:
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"
    if not parsed.path:
        transformations.append("insert_root_path")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        transformations.append("remove_trailing_path_slash")
    fragment = ""
    if parsed.fragment:
        transformations.append("drop_fragment")
    canonical = urlunsplit((scheme, netloc, path, parsed.query, fragment))
    return canonical, transformations


def _route_kind(canonical: str) -> UrlRouteKind:
    parsed = urlsplit(canonical)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    if host in {"t.me", "telegram.me"}:
        return UrlRouteKind.PUBLIC_CHANNEL
    if host in {"vk.ru", "vk.com"}:
        return UrlRouteKind.PUBLIC_CHANNEL
    if host == "vkvideo.ru":
        if path.endswith("/clips") or "/playlist/" in path:
            return UrlRouteKind.PUBLIC_COLLECTION
        if "/video-" in path or "/video" in path:
            return UrlRouteKind.PUBLIC_MEDIA
        return UrlRouteKind.PUBLIC_CHANNEL
    if host in {"youtube.com", "www.youtube.com"}:
        if path == "/playlist" or path.endswith("/playlists"):
            return UrlRouteKind.PUBLIC_COLLECTION
        if path == "/watch" or path.startswith("/shorts/"):
            return UrlRouteKind.PUBLIC_MEDIA
        return UrlRouteKind.PUBLIC_CHANNEL
    if host == "youtu.be":
        return UrlRouteKind.PUBLIC_MEDIA
    if host in {"rutube.ru", "www.rutube.ru"} and path.startswith("/channel/"):
        return UrlRouteKind.PUBLIC_CHANNEL
    if path == "/":
        return UrlRouteKind.PUBLIC_SITE
    return UrlRouteKind.PUBLIC_PROFILE


def _is_author_admin_route(canonical: str) -> bool:
    parsed = urlsplit(canonical)
    host = (parsed.hostname or "").lower()
    if host in _ADMIN_HOSTS:
        return True
    segments = {segment.casefold() for segment in parsed.path.split("/") if segment}
    if segments & _ADMIN_PATH_SEGMENTS:
        return True
    return any(
        key.casefold() in {"act", "action", "mode", "section", "view"} and value.casefold() in _ADMIN_QUERY_VALUES
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    )


def canonicalize_http_url(value: str) -> CanonicalUrlEvidence:
    canonical, transformations = _canonical_url_parts(value)
    payload = {
        "ruleset_version": _RULESET_VERSION,
        "original": value,
        "canonical": canonical,
        "transformations": transformations,
        "project_key": None,
        "route_kind": None,
    }
    return CanonicalUrlEvidence(
        original=value,
        canonical=canonical,
        transformations=transformations,
        digest=evidence_digest(payload),
    )


def canonicalize_public_url(value: str) -> CanonicalUrlEvidence:
    canonical, transformations = _canonical_url_parts(value)
    if _is_author_admin_route(canonical):
        raise ValueError(f"Author/admin URL is not allowed in public identity: {canonical}")
    route_kind = _route_kind(canonical)
    payload = {
        "ruleset_version": _RULESET_VERSION,
        "original": value,
        "canonical": canonical,
        "transformations": transformations,
        "project_key": None,
        "route_kind": route_kind.value,
    }
    return CanonicalUrlEvidence(
        original=value,
        canonical=canonical,
        transformations=transformations,
        route_kind=route_kind,
        digest=evidence_digest(payload),
    )


def canonicalize_project_url(
    value: str,
    *,
    expected_project_key: str,
    project_profiles: Mapping[str, Iterable[str]],
) -> CanonicalUrlEvidence:
    if expected_project_key not in project_profiles:
        raise ValueError(f"Unknown project profile: {expected_project_key}")

    public_evidence = canonicalize_public_url(value)
    canonical = public_evidence.canonical
    transformations = public_evidence.transformations

    owners: dict[str, set[str]] = {}
    for project_key, urls in project_profiles.items():
        for profile_url in urls:
            profile_canonical, _ = _canonical_url_parts(profile_url)
            owners.setdefault(profile_canonical, set()).add(project_key)
    duplicate_owners = owners.get(canonical, set())
    if len(duplicate_owners) > 1:
        raise ValueError(f"URL belongs to multiple project profiles: {canonical}")
    if duplicate_owners and expected_project_key not in duplicate_owners:
        foreign_project = next(iter(duplicate_owners))
        raise ValueError(f"URL belongs to another project profile {foreign_project}: {canonical}")
    if expected_project_key not in duplicate_owners:
        raise ValueError(f"URL is not approved for project {expected_project_key}: {canonical}")

    route_kind = _route_kind(canonical)
    payload = {
        "ruleset_version": _RULESET_VERSION,
        "original": value,
        "canonical": canonical,
        "transformations": transformations,
        "project_key": expected_project_key,
        "route_kind": route_kind.value,
    }
    return CanonicalUrlEvidence(
        original=value,
        canonical=canonical,
        transformations=transformations,
        project_key=expected_project_key,
        route_kind=route_kind,
        digest=evidence_digest(payload),
    )
