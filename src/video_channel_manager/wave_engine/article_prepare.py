from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx

from video_channel_manager.platforms.http import (
    HttpClientOwner,
    HttpOperationClass,
    execute_http_request,
)
from video_channel_manager.platforms.vk.text_writer import canonical_vk_text
from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    object_sha256,
    write_json_atomic,
)
from video_channel_manager.wave_engine.models import (
    EvidenceArtifact,
    MutationClass,
    ProjectBinding,
    WaveApplyIntent,
    WaveOperationSpec,
    WavePlan,
    WaveSourceEvidence,
)
from video_channel_manager.wave_engine.vk_article_provider import (
    VK_ARTICLE_ACCOUNT_ALIAS,
    VK_ARTICLE_COMMUNITY_ID,
    VK_ARTICLE_OPERATION_KIND,
    VK_ARTICLE_OWNER_ID,
    VK_ARTICLE_PROJECT_KEY,
    VK_ARTICLE_SITE_HOST,
    jpeg_dimensions,
)

APPROVED_POLICY_SCHEMA = "video-manager.vk-legendary-poet-article-wave-policy"
APPROVED_POLICY_VERSION = 1
ARTICLE_POLICY_VERSION = "legendary-poet-article-photo-wave-202608-v1"
RAW_GITHUB_BASE = "https://raw.githubusercontent.com"
JPEG_WIDTH = 1200
JPEG_HEIGHT = 630


class ArticlePreparationError(RuntimeError):
    pass


class _ArticleHttpClient(HttpClientOwner):
    def __init__(self) -> None:
        self._initialize_http_client(
            None,
            timeout=60.0,
            follow_redirects=True,
        )
        self._http_client.headers.update(
            {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/148 Safari/537.36")
            }
        )

    def get(self, url: str) -> httpx.Response:
        result = execute_http_request(
            lambda: self._http_client.get(url),
            provider="article-source",
            operation=HttpOperationClass.SAFE_READ,
            method="GET",
            resource=urlsplit(url).path or "/",
        )
        return result.response


class _PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical = ""
        self.og_url = ""
        self.og_image = ""
        self.og_title = ""
        self.og_description = ""
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "").strip() for key, value in attrs}
        if tag.lower() == "link" and "canonical" in values.get("rel", "").lower().split():
            self.canonical = values.get("href", "")
            return
        if tag.lower() != "meta":
            return
        key = (values.get("property") or values.get("name") or "").lower()
        content = values.get("content", "")
        if key == "og:url":
            self.og_url = content
        elif key == "og:image":
            self.og_image = content
        elif key == "og:title":
            self.og_title = content
        elif key == "og:description":
            self.og_description = content
        elif key == "robots":
            self.robots.append(content.lower())


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ArticlePreparationError(f"URL has an invalid port: {value}") from exc
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _https_url(value: object, *, field: str, required_host: str | None = None) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ArticlePreparationError(f"{field} must be an exact non-empty string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ArticlePreparationError(f"{field} must be an absolute HTTPS URL")
    if required_host is not None and (parsed.hostname or "").lower() != required_host:
        raise ArticlePreparationError(f"{field} must use host {required_host}")
    return value


def _relative_posix(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ArticlePreparationError(f"{field} must be an exact non-empty path")
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if value != normalized or candidate.is_absolute() or ".." in candidate.parts or value in {".", ""}:
        raise ArticlePreparationError(f"{field} must be a normalized repository-relative path")
    return value


def _policy_digest(policy: dict[str, Any]) -> str:
    payload = {key: value for key, value in policy.items() if key != "policy_sha256"}
    return "sha256:" + object_sha256(payload)


def _message_digest(message: str) -> str:
    return "sha256:" + hashlib.sha256(message.encode("utf-8")).hexdigest()


def load_approved_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArticlePreparationError(f"Cannot read approved policy: {exc}") from exc
    if not isinstance(policy, dict):
        raise ArticlePreparationError("Approved policy must be a JSON object")
    exact_identity = {
        "schema_name": APPROVED_POLICY_SCHEMA,
        "schema_version": APPROVED_POLICY_VERSION,
        "project_key": VK_ARTICLE_PROJECT_KEY,
        "vk_community_id": VK_ARTICLE_COMMUNITY_ID,
        "vk_owner_id": VK_ARTICLE_OWNER_ID,
        "account_alias": VK_ARTICLE_ACCOUNT_ALIAS,
        "attachment_mode": "explicit-wall-photo-plus-text-link",
        "source_repository": "FedorMilovanov/TheLegendaryPoet",
    }
    for field, expected in exact_identity.items():
        if policy.get(field) != expected:
            raise ArticlePreparationError(f"Approved policy {field} mismatch: {policy.get(field)!r} != {expected!r}")
    if policy.get("policy_sha256") != _policy_digest(policy):
        raise ArticlePreparationError("Approved policy self-digest mismatch")
    commit = str(policy.get("source_repository_commit") or "")
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ArticlePreparationError("source_repository_commit must be a lowercase Git SHA")
    operations = policy.get("operations")
    if not isinstance(operations, list) or len(operations) != 10:
        raise ArticlePreparationError("Approved policy must contain exactly ten operations")

    seen_ids: set[str] = set()
    previous_publish_date: int | None = None
    for ordinal, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise ArticlePreparationError(f"Operation {ordinal} must be an object")
        if operation.get("ordinal") != ordinal:
            raise ArticlePreparationError(f"Operation {ordinal} has a wrong ordinal")
        editorial_id = str(operation.get("operation_id") or "")
        if not editorial_id or editorial_id in seen_ids:
            raise ArticlePreparationError(f"Operation {ordinal} has a blank or duplicate ID")
        seen_ids.add(editorial_id)
        article_url = _https_url(
            operation.get("url"),
            field=f"operations[{ordinal}].url",
            required_host=VK_ARTICLE_SITE_HOST,
        )
        _https_url(operation.get("image_url"), field=f"operations[{ordinal}].image_url")
        _relative_posix(operation.get("source_path"), field=f"operations[{ordinal}].source_path")
        image_source_path = operation.get("image_source_path")
        if image_source_path is not None:
            _relative_posix(
                image_source_path,
                field=f"operations[{ordinal}].image_source_path",
            )
        message = str(operation.get("message") or "")
        if message != canonical_vk_text(message) or not message:
            raise ArticlePreparationError(f"Operation {ordinal} message is not canonical VK text")
        if message.count(article_url) != 1:
            raise ArticlePreparationError(f"Operation {ordinal} must contain its exact article URL once")
        if operation.get("message_sha256") != _message_digest(message):
            raise ArticlePreparationError(f"Operation {ordinal} message digest mismatch")
        publish_date = operation.get("publish_date")
        if type(publish_date) is not int or publish_date <= 0:
            raise ArticlePreparationError(f"Operation {ordinal} publish_date is invalid")
        try:
            publish_at = datetime.fromisoformat(str(operation.get("publish_at") or ""))
        except ValueError as exc:
            raise ArticlePreparationError(f"Operation {ordinal} publish_at is invalid") from exc
        offset = publish_at.utcoffset()
        if publish_at.tzinfo is None or offset is None:
            raise ArticlePreparationError(f"Operation {ordinal} publish_at lacks a timezone")
        if int(publish_at.timestamp()) != publish_date:
            raise ArticlePreparationError(f"Operation {ordinal} publish time mismatch")
        if offset.total_seconds() != 3 * 3600:
            raise ArticlePreparationError(f"Operation {ordinal} must use UTC+03:00")
        if publish_at.hour != 19 or publish_at.minute != 0:
            raise ArticlePreparationError(f"Operation {ordinal} must be scheduled for 19:00")
        if previous_publish_date is not None and publish_date - previous_publish_date != 2 * 86400:
            raise ArticlePreparationError("Approved schedule is not exactly every two days")
        previous_publish_date = publish_date
        markers = operation.get("source_markers")
        if (
            not isinstance(markers, list)
            or len(markers) < 2
            or any(not isinstance(marker, str) or not marker for marker in markers)
        ):
            raise ArticlePreparationError(f"Operation {ordinal} requires at least two exact source markers")
    return policy


def _raw_source_url(policy: dict[str, Any], relative_path: str) -> str:
    owner, repository = str(policy["source_repository"]).split("/", maxsplit=1)
    encoded_path = "/".join(quote(part) for part in PurePosixPath(relative_path).parts)
    return f"{RAW_GITHUB_BASE}/{quote(owner)}/{quote(repository)}/{policy['source_repository_commit']}/{encoded_path}"


def _get(http: _ArticleHttpClient, url: str, *, label: str) -> httpx.Response:
    try:
        response = http.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ArticlePreparationError(f"{label} request failed: {url}: {exc}") from exc
    return response


def _verify_page(
    http: _ArticleHttpClient,
    *,
    operation: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    article_url = str(operation["url"])
    response = _get(http, article_url, label="article page")
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        raise ArticlePreparationError(f"Article page is not HTML: {article_url}: {content_type}")
    metadata = _PageMetadata()
    metadata.feed(response.text)
    canonical = _canonical_url(urljoin(article_url, metadata.canonical or article_url))
    og_url = _canonical_url(urljoin(article_url, metadata.og_url or canonical))
    expected_url = _canonical_url(article_url)
    image_url = _canonical_url(urljoin(article_url, metadata.og_image))
    expected_image = _canonical_url(str(operation["image_url"]))
    if canonical != expected_url or og_url != expected_url:
        raise ArticlePreparationError(
            f"Article canonical/og:url mismatch: {canonical!r}, {og_url!r}, expected {expected_url!r}"
        )
    if image_url != expected_image:
        raise ArticlePreparationError(f"Article og:image mismatch: {image_url!r} != {expected_image!r}")
    if len(metadata.og_title.strip()) < 12:
        raise ArticlePreparationError(f"Article has no usable og:title: {article_url}")
    if len(metadata.og_description.strip()) < 60:
        raise ArticlePreparationError(f"Article has no usable og:description: {article_url}")
    if any("noindex" in directive for directive in metadata.robots):
        raise ArticlePreparationError(f"Article is marked noindex: {article_url}")
    return metadata.og_image, {
        "canonical_url": canonical,
        "og_url": og_url,
        "og_image": image_url,
        "og_title": metadata.og_title,
        "og_description": metadata.og_description,
    }


def _verify_pinned_source(
    http: _ArticleHttpClient,
    *,
    policy: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, Any]:
    source_url = _raw_source_url(policy, str(operation["source_path"]))
    response = _get(http, source_url, label="pinned article source")
    try:
        text = response.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArticlePreparationError(f"Pinned article source is not UTF-8: {operation['source_path']}") from exc
    missing = [marker for marker in operation["source_markers"] if marker not in text]
    if missing:
        raise ArticlePreparationError(
            f"Pinned article source is missing markers for {operation['operation_id']}: {missing!r}"
        )
    return {
        "source_url": source_url,
        "source_path": operation["source_path"],
        "bytes": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "markers": list(operation["source_markers"]),
    }


def _suffix_for_image(url: str, content_type: str) -> str:
    lowered = content_type.lower()
    if "webp" in lowered:
        return ".webp"
    if "png" in lowered:
        return ".png"
    if "jpeg" in lowered or "jpg" in lowered:
        return ".jpg"
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".webp", ".png", ".jpg", ".jpeg"} else ".img"


def _materialize_jpeg(
    *,
    ffmpeg: str,
    source_bytes: bytes,
    source_url: str,
    content_type: str,
    output_path: Path,
) -> bytes:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vcm-article-image-") as temporary:
        input_path = Path(temporary) / f"source{_suffix_for_image(source_url, content_type)}"
        input_path.write_bytes(source_bytes)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"scale={JPEG_WIDTH}:{JPEG_HEIGHT}:force_original_aspect_ratio=increase,crop={JPEG_WIDTH}:{JPEG_HEIGHT}",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise ArticlePreparationError(f"ffmpeg image conversion failed: {completed.stderr.strip()}")
    jpeg = output_path.read_bytes()
    if jpeg_dimensions(jpeg) != (JPEG_WIDTH, JPEG_HEIGHT):
        raise ArticlePreparationError("Materialized JPEG dimensions are not 1200x630")
    return jpeg


def _verify_local_image_source(
    http: _ArticleHttpClient,
    *,
    policy: dict[str, Any],
    operation: dict[str, Any],
    live_bytes: bytes,
) -> dict[str, Any] | None:
    source_path = operation.get("image_source_path")
    if source_path is None:
        return None
    source_url = _raw_source_url(policy, str(source_path))
    response = _get(http, source_url, label="pinned image source")
    pinned_sha = hashlib.sha256(response.content).hexdigest()
    live_sha = hashlib.sha256(live_bytes).hexdigest()
    if pinned_sha != live_sha:
        raise ArticlePreparationError(
            f"Live image differs from pinned source for {operation['operation_id']}: {live_sha} != {pinned_sha}"
        )
    return {
        "source_url": source_url,
        "source_path": source_path,
        "bytes": len(response.content),
        "sha256": pinned_sha,
    }


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _repo_relative(repository_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository_root.resolve()).as_posix()
    except ValueError as exc:
        raise ArticlePreparationError(f"Path escapes repository root: {path}") from exc


def _build_specs(
    *,
    operations: list[dict[str, Any]],
    assets_by_editorial_id: dict[str, dict[str, Any]],
    policy_sha256: str,
    required_canary: dict[str, Any] | None,
) -> tuple[WaveOperationSpec, ...]:
    specs: list[WaveOperationSpec] = []
    for operation in operations:
        editorial_id = str(operation["operation_id"])
        asset = assets_by_editorial_id[editorial_id]
        seed = f"{policy_sha256}:{editorial_id}:{operation['publish_date']}:{operation['message_sha256']}"
        guid = "vcm-art-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:28]
        payload: dict[str, Any] = {
            "editorial_operation_id": editorial_id,
            "account_alias": VK_ARTICLE_ACCOUNT_ALIAS,
            "article_url": operation["url"],
            "image_source_url": operation["image_url"],
            "message": operation["message"],
            "message_sha256": operation["message_sha256"],
            "publish_date": operation["publish_date"],
            "publish_at": operation["publish_at"],
            "guid": guid,
            "asset_path": asset["asset_path"],
            "asset_sha256": asset["asset_sha256"],
            "asset_width": JPEG_WIDTH,
            "asset_height": JPEG_HEIGHT,
            "policy_sha256": policy_sha256,
            "required_canary": required_canary,
        }
        specs.append(
            WaveOperationSpec(
                order_key=f"{int(operation['ordinal']):02d}-{operation['id']}",
                operation_kind=VK_ARTICLE_OPERATION_KIND,
                mutation_class=MutationClass.AMBIGUOUS_MUTATION,
                payload=payload,
            )
        )
    return tuple(specs)


def _build_wave_documents(
    *,
    repository_root: Path,
    scope_directory: Path,
    policy_path: Path,
    asset_manifest_path: Path,
    all_asset_paths: list[Path],
    policy_version: str,
    specs: tuple[WaveOperationSpec, ...],
) -> dict[str, Any]:
    scope_directory.mkdir(parents=True, exist_ok=True)
    journal_directory = scope_directory / "journal"
    if journal_directory.exists():
        raise ArticlePreparationError(
            f"Journal already exists; automatic replay/preparation is prohibited: {journal_directory}"
        )

    operations_path = scope_directory / "operations.json"
    write_json_atomic(operations_path, [spec.model_dump(mode="json") for spec in specs])
    artifact_paths = [policy_path, asset_manifest_path, operations_path, *all_asset_paths]
    artifacts = tuple(
        EvidenceArtifact(
            path=_repo_relative(repository_root, path),
            sha256=file_sha256(path),
        )
        for path in sorted(artifact_paths, key=lambda value: _repo_relative(repository_root, value))
    )
    source = WaveSourceEvidence.build(
        project=ProjectBinding(
            project_key=VK_ARTICLE_PROJECT_KEY,
            community_id=VK_ARTICLE_COMMUNITY_ID,
            owner_id=VK_ARTICLE_OWNER_ID,
        ),
        policy_version=policy_version,
        artifacts=artifacts,
    )
    source_path = scope_directory / "source.json"
    write_json_atomic(source_path, source.model_dump(mode="json"))
    plan = WavePlan.build(source=source, specs=specs)
    plan_path = scope_directory / "plan.json"
    write_json_atomic(plan_path, plan.model_dump(mode="json"))
    intent = WaveApplyIntent.build(
        source=source,
        source_path=_repo_relative(repository_root, source_path),
        source_file_sha256=file_sha256(source_path),
        plan=plan,
        plan_path=_repo_relative(repository_root, plan_path),
        plan_file_sha256=file_sha256(plan_path),
        enable_provider_writes=True,
    )
    intent_path = scope_directory / "intent.json"
    write_json_atomic(intent_path, intent.model_dump(mode="json"))

    manifest_path = scope_directory / "operator-manifest.json"
    manifest = {
        "schema_name": "video-manager.operator-manifest",
        "schema_version": 1,
        "project_key": VK_ARTICLE_PROJECT_KEY,
        "community_id": VK_ARTICLE_COMMUNITY_ID,
        "owner_id": VK_ARTICLE_OWNER_ID,
        "source_snapshot_id": source.source_snapshot_id,
        "operation_count": len(plan.operations),
        "operation_class": "ambiguous_mutation",
        "provider_mutation": True,
        "entrypoint_id": "video-manager-cli",
        "arguments": [
            "wave",
            "apply",
            "--source",
            _repo_relative(repository_root, source_path),
            "--plan",
            _repo_relative(repository_root, plan_path),
            "--intent",
            _repo_relative(repository_root, intent_path),
            "--repository-root",
            str(repository_root.resolve()),
            "--journal-directory",
            _repo_relative(repository_root, journal_directory),
            "--vk-account",
            VK_ARTICLE_ACCOUNT_ALIAS,
            "--enable-provider-writes",
        ],
    }
    write_json_atomic(manifest_path, manifest)
    request_path = scope_directory / "operator-request.json"
    manifest_sha256 = file_sha256(manifest_path)
    request = {
        "schema_name": "video-manager.operator-request",
        "schema_version": 1,
        "mode": "apply",
        "manifest_path": _repo_relative(repository_root, manifest_path),
        "manifest_sha256": manifest_sha256,
        "confirm_manifest_sha256": manifest_sha256,
        "confirm_project_key": VK_ARTICLE_PROJECT_KEY,
        "confirm_community_id": VK_ARTICLE_COMMUNITY_ID,
        "confirm_owner_id": VK_ARTICLE_OWNER_ID,
        "confirm_source_snapshot_id": source.source_snapshot_id,
        "confirm_operation_count": len(plan.operations),
    }
    write_json_atomic(request_path, request)
    return {
        "scope": scope_directory.name,
        "operation_count": len(plan.operations),
        "source_snapshot_id": source.source_snapshot_id,
        "source_self_digest": source.self_digest,
        "plan_self_digest": plan.self_digest,
        "operation_set_digest": plan.operation_set_digest,
        "intent_self_digest": intent.self_digest,
        "request_path": _repo_relative(repository_root, request_path),
        "request_sha256": file_sha256(request_path),
        "manifest_path": _repo_relative(repository_root, manifest_path),
        "manifest_sha256": manifest_sha256,
        "journal_path": _repo_relative(repository_root, journal_directory),
        "operator_output_path": _repo_relative(repository_root, scope_directory / "operator-output"),
    }


def prepare_legendary_poet_article_wave(
    *,
    policy_path: Path,
    repository_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = repository_root.resolve()
    policy_path = policy_path.resolve()
    output_root = output_root.resolve()
    try:
        policy_path.relative_to(root)
        output_root.relative_to(root)
    except ValueError as exc:
        raise ArticlePreparationError("Policy and output root must remain inside the repository root") from exc
    if output_root.exists() and any(output_root.iterdir()):
        raise ArticlePreparationError(f"Output root is not empty; preparation will not overwrite it: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    policy = load_approved_policy(policy_path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ArticlePreparationError("ffmpeg is required to materialize JPEG 1200x630 assets")

    assets_directory = output_root / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)
    asset_rows: list[dict[str, Any]] = []
    all_asset_paths: list[Path] = []
    with _ArticleHttpClient() as http:
        for operation in policy["operations"]:
            editorial_id = str(operation["operation_id"])
            live_image_url, metadata = _verify_page(http, operation=operation)
            source_evidence = _verify_pinned_source(
                http,
                policy=policy,
                operation=operation,
            )
            image_response = _get(http, live_image_url, label="article cover")
            if not image_response.headers.get("content-type", "").lower().startswith("image/"):
                raise ArticlePreparationError(f"Article cover is not an image: {live_image_url}")
            local_image_evidence = _verify_local_image_source(
                http,
                policy=policy,
                operation=operation,
                live_bytes=image_response.content,
            )
            asset_path = assets_directory / f"{int(operation['ordinal']):02d}-{operation['id']}.jpg"
            jpeg = _materialize_jpeg(
                ffmpeg=ffmpeg,
                source_bytes=image_response.content,
                source_url=live_image_url,
                content_type=image_response.headers.get("content-type", ""),
                output_path=asset_path,
            )
            all_asset_paths.append(asset_path)
            asset_rows.append(
                {
                    "ordinal": operation["ordinal"],
                    "editorial_operation_id": editorial_id,
                    "article_url": operation["url"],
                    "page_metadata": metadata,
                    "pinned_source": source_evidence,
                    "image_source_url": live_image_url,
                    "live_image_bytes": len(image_response.content),
                    "live_image_sha256": hashlib.sha256(image_response.content).hexdigest(),
                    "pinned_image_source": local_image_evidence,
                    "asset_path": _repo_relative(root, asset_path),
                    "asset_bytes": len(jpeg),
                    "asset_sha256": hashlib.sha256(jpeg).hexdigest(),
                    "asset_width": JPEG_WIDTH,
                    "asset_height": JPEG_HEIGHT,
                }
            )

    asset_manifest = {
        "schema_name": "video-manager.legendary-poet-article-assets",
        "schema_version": 1,
        "project_key": VK_ARTICLE_PROJECT_KEY,
        "source_repository": policy["source_repository"],
        "source_repository_commit": policy["source_repository_commit"],
        "policy_sha256": policy["policy_sha256"],
        "items": asset_rows,
    }
    asset_manifest["manifest_sha256"] = object_sha256(asset_manifest)
    asset_manifest_path = output_root / "asset-manifest.json"
    write_json_atomic(asset_manifest_path, asset_manifest)
    assets_by_editorial_id = {str(item["editorial_operation_id"]): item for item in asset_rows}

    canary_operation = policy["operations"][0]
    canary_specs = _build_specs(
        operations=[canary_operation],
        assets_by_editorial_id=assets_by_editorial_id,
        policy_sha256=str(policy["policy_sha256"]),
        required_canary=None,
    )
    canary_requirement = {
        "editorial_operation_id": canary_operation["operation_id"],
        "article_url": canary_operation["url"],
        "message": canary_operation["message"],
        "message_sha256": canary_operation["message_sha256"],
        "publish_date": canary_operation["publish_date"],
    }
    batch_specs = _build_specs(
        operations=list(policy["operations"][1:]),
        assets_by_editorial_id=assets_by_editorial_id,
        policy_sha256=str(policy["policy_sha256"]),
        required_canary=canary_requirement,
    )
    canary = _build_wave_documents(
        repository_root=root,
        scope_directory=output_root / "canary",
        policy_path=policy_path,
        asset_manifest_path=asset_manifest_path,
        all_asset_paths=all_asset_paths,
        policy_version=f"{ARTICLE_POLICY_VERSION}-canary",
        specs=canary_specs,
    )
    batch = _build_wave_documents(
        repository_root=root,
        scope_directory=output_root / "batch",
        policy_path=policy_path,
        asset_manifest_path=asset_manifest_path,
        all_asset_paths=all_asset_paths,
        policy_version=f"{ARTICLE_POLICY_VERSION}-batch",
        specs=batch_specs,
    )
    summary: dict[str, Any] = {
        "schema_name": "video-manager.legendary-poet-article-preparation",
        "schema_version": 1,
        "status": "prepared",
        "project_key": VK_ARTICLE_PROJECT_KEY,
        "community_id": VK_ARTICLE_COMMUNITY_ID,
        "owner_id": VK_ARTICLE_OWNER_ID,
        "policy_path": _repo_relative(root, policy_path),
        "policy_sha256": policy["policy_sha256"],
        "asset_manifest_path": _repo_relative(root, asset_manifest_path),
        "asset_manifest_sha256": asset_manifest["manifest_sha256"],
        "assets": len(asset_rows),
        "canary": canary,
        "batch": batch,
    }
    summary["preparation_sha256"] = object_sha256(summary)
    summary_path = output_root / "preparation-summary.json"
    write_json_atomic(summary_path, summary)

    readme = f"""# Legendary Poet article wave — prepared

Project: `{VK_ARTICLE_PROJECT_KEY}`  
VK community: `{VK_ARTICLE_COMMUNITY_ID}`  
VK owner: `{VK_ARTICLE_OWNER_ID}`  
Approved policy: `{summary["policy_sha256"]}`  
Assets: `{len(asset_rows)}` JPEG files, each {JPEG_WIDTH}×{JPEG_HEIGHT}

## Canary

Request: `{canary["request_path"]}`  
Expected request SHA-256: `{canary["request_sha256"]}`  
Operations: 1

Run the supported PowerShell operator with `-EnableProviderWrites`.
Do not run the batch unless the canary Wave result is `succeeded` and the exact
postponed post is visible with its text, date, article URL, and one photo.

## Batch

Request: `{batch["request_path"]}`  
Expected request SHA-256: `{batch["request_sha256"]}`  
Operations: 9

Every batch operation independently requires the exact postponed canary.
An absent or ambiguous canary stops before a provider mutation.

## Unknown outcome

A nonzero apply result for this ambiguous mutation is never retry-safe.
Do not delete a journal or rerun the request. Build a reconciliation request
from the exact Wave result and use `video-manager wave reconcile`.
"""
    _write_text_atomic(output_root / "README.md", readme)
    return summary


__all__ = [
    "APPROVED_POLICY_SCHEMA",
    "APPROVED_POLICY_VERSION",
    "ARTICLE_POLICY_VERSION",
    "ArticlePreparationError",
    "load_approved_policy",
    "prepare_legendary_poet_article_wave",
]
