from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel, TypeAdapter, ValidationError
from rich.console import Console
from rich.table import Table

from video_channel_manager.wave_engine.article_prepare import (
    ArticlePreparationError,
    prepare_legendary_poet_article_wave,
)
from video_channel_manager.wave_engine.canonical import (
    file_sha256,
    read_json_object,
    resolve_repository_relative_path,
    write_json_atomic,
)
from video_channel_manager.wave_engine.engine import WaveEngine
from video_channel_manager.wave_engine.models import (
    WAVE_SCHEMA_MODELS,
    WaveApplyIntent,
    WaveOperationSpec,
    WavePlan,
    WaveReconciliationRequest,
    WaveReconciliationResult,
    WaveResult,
    WaveSourceEvidence,
    WaveStatus,
)
from video_channel_manager.wave_engine.vk_article_provider import (
    VK_ARTICLE_ACCOUNT_ALIAS,
    VK_ARTICLE_OPERATION_KIND,
    VkPostponedArticlePhotoAdapter,
)


wave_app = typer.Typer(no_args_is_help=True, help="Versioned fail-closed wave engine.")
source_app = typer.Typer(no_args_is_help=True, help="Verify exact source evidence.")
wave_plan_app = typer.Typer(no_args_is_help=True, help="Build and validate versioned wave plans.")
result_app = typer.Typer(no_args_is_help=True, help="Verify structured wave results.")
article_app = typer.Typer(no_args_is_help=True, help="Prepare reviewed article publication waves.")
wave_app.add_typer(source_app, name="source")
wave_app.add_typer(wave_plan_app, name="plan")
wave_app.add_typer(result_app, name="result")
wave_app.add_typer(article_app, name="article")
console = Console()
_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _read_model(path: Path, model: type[_ModelT]) -> _ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8-sig"), strict=True)
    except (OSError, ValidationError) as exc:
        raise typer.BadParameter(f"Invalid {model.__name__}: {exc}", param_hint=str(path)) from exc


@source_app.command("verify")
def source_verify(
    path: Path,
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
) -> None:
    source = _read_model(path, WaveSourceEvidence)
    try:
        source.verify_artifacts(repository_root)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint=str(repository_root)) from exc
    console.print(f"[green]Valid source evidence:[/green] {source.self_digest}")


@wave_plan_app.command("build")
def plan_build(
    source_path: Annotated[Path, typer.Option("--source")],
    operations_path: Annotated[Path, typer.Option("--operations")],
    output: Annotated[Path, typer.Option("--output", "-o")],
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
) -> None:
    source = _read_model(source_path, WaveSourceEvidence)
    try:
        source.verify_artifacts(repository_root)
        raw_text = operations_path.read_text(encoding="utf-8-sig")
        specs = tuple(TypeAdapter(list[WaveOperationSpec]).validate_json(raw_text, strict=True))
        plan = WavePlan.build(source=source, specs=specs)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise typer.BadParameter(f"Invalid plan input: {exc}") from exc
    write_json_atomic(output, plan.model_dump(mode="json"))
    console.print(f"[green]Built {len(plan.operations)} operations:[/green] {plan.self_digest}")


@wave_plan_app.command("validate")
def plan_validate(path: Path) -> None:
    plan = _read_model(path, WavePlan)
    console.print(f"[green]Valid wave plan:[/green] {plan.self_digest}")


@article_app.command("prepare")
def article_prepare(
    policy_path: Annotated[Path, typer.Argument(help="Approved article-wave policy JSON")],
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
    output_root: Annotated[
        Path,
        typer.Option("--output-root", "-o"),
    ] = Path("data/operator/legendary-poet-article-wave-202608"),
) -> None:
    """Verify article sources/covers and build canary plus batch operator evidence."""

    try:
        summary = prepare_legendary_poet_article_wave(
            policy_path=policy_path,
            repository_root=repository_root,
            output_root=output_root,
        )
    except (ArticlePreparationError, OSError, ValueError) as exc:
        console.print(f"[red]Article wave preparation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(
        f"[green]Prepared Legendary Poet article wave:[/green] "
        f"{summary['assets']} assets; policy={summary['policy_sha256']}"
    )
    console.print(f"Canary request: {summary['canary']['request_path']} sha256={summary['canary']['request_sha256']}")
    console.print(f"Batch request: {summary['batch']['request_path']} sha256={summary['batch']['request_sha256']}")


@wave_app.command("preview")
def preview(path: Path) -> None:
    plan = _read_model(path, WavePlan)
    table = Table(title="Wave plan preview")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Project", plan.project.project_key)
    table.add_row("Community", str(plan.project.community_id))
    table.add_row("Owner", str(plan.project.owner_id))
    table.add_row("Source snapshot", plan.source_snapshot_id)
    table.add_row("Policy", plan.policy_version)
    table.add_row("Operations", str(len(plan.operations)))
    table.add_row("Operation set", plan.operation_set_digest)
    table.add_row("Plan digest", plan.self_digest)
    console.print(table)


def _validated_apply_documents(
    *,
    source_path: Path,
    plan_path: Path,
    intent_path: Path,
    repository_root: Path,
    enable_provider_writes: bool,
) -> tuple[WaveSourceEvidence, WavePlan, WaveApplyIntent]:
    source = _read_model(source_path, WaveSourceEvidence)
    plan = _read_model(plan_path, WavePlan)
    intent = _read_model(intent_path, WaveApplyIntent)
    intent.assert_matches(plan, source)
    try:
        expected_source_path = resolve_repository_relative_path(repository_root, intent.source_path, require_file=True)
        expected_plan_path = resolve_repository_relative_path(repository_root, intent.plan_path, require_file=True)
        source.verify_artifacts(repository_root)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint=str(intent_path)) from exc
    if source_path.resolve() != expected_source_path:
        raise typer.BadParameter(
            "source path differs from the exact apply-intent source_path",
            param_hint=str(source_path),
        )
    if file_sha256(source_path) != intent.source_file_sha256:
        raise typer.BadParameter(
            "source evidence file SHA-256 differs from the apply intent",
            param_hint=str(source_path),
        )
    if plan_path.resolve() != expected_plan_path:
        raise typer.BadParameter(
            "plan path differs from the exact apply-intent plan_path",
            param_hint=str(plan_path),
        )
    if file_sha256(plan_path) != intent.plan_file_sha256:
        raise typer.BadParameter(
            "plan file SHA-256 differs from the apply intent",
            param_hint=str(plan_path),
        )
    if intent.enable_provider_writes != enable_provider_writes:
        raise typer.BadParameter("provider-write confirmation differs from the apply intent")
    return source, plan, intent


def _article_plan(plan: WavePlan) -> bool:
    return bool(plan.operations) and {operation.operation_kind for operation in plan.operations} == {
        VK_ARTICLE_OPERATION_KIND
    }


@wave_app.command("apply")
def apply(
    source_path: Annotated[Path, typer.Option("--source")],
    plan_path: Annotated[Path, typer.Option("--plan")],
    intent_path: Annotated[Path, typer.Option("--intent")],
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
    journal_directory: Annotated[Path | None, typer.Option("--journal-directory")] = None,
    vk_account: Annotated[str, typer.Option("--vk-account")] = VK_ARTICLE_ACCOUNT_ALIAS,
    enable_provider_writes: Annotated[bool, typer.Option("--enable-provider-writes")] = False,
) -> None:
    source, plan, intent = _validated_apply_documents(
        source_path=source_path,
        plan_path=plan_path,
        intent_path=intent_path,
        repository_root=repository_root,
        enable_provider_writes=enable_provider_writes,
    )
    if not _article_plan(plan):
        console.print(
            "[red]Rejected:[/red] no reviewed production provider adapter is registered for this operation set."
        )
        raise typer.Exit(code=3)
    if journal_directory is None:
        raise typer.BadParameter(
            "Legendary Poet article apply requires --journal-directory",
            param_hint="--journal-directory",
        )
    try:
        adapter = VkPostponedArticlePhotoAdapter(
            repository_root=repository_root,
            account_alias=vk_account,
        )
        result = WaveEngine().apply(
            source=source,
            plan=plan,
            intent=intent,
            adapter=adapter,
            repository_root=repository_root,
            source_file_path=source_path,
            plan_file_path=plan_path,
            journal_directory=journal_directory,
            provider_writes_enabled=enable_provider_writes,
        )
    except (OSError, ValueError) as exc:
        console.print(f"[red]Article wave apply rejected:[/red] {exc}")
        raise typer.Exit(code=3) from exc

    if result.status is WaveStatus.SUCCEEDED:
        console.print(
            f"[green]Article wave succeeded:[/green] {len(result.operations)} operation(s); "
            f"result={journal_directory / 'result.json'}"
        )
        return
    if result.status is WaveStatus.UNKNOWN_REQUIRES_RECONCILIATION:
        console.print(
            "[red]Article wave outcome requires reconciliation.[/red] "
            f"Do not retry. Result: {journal_directory / 'result.json'}"
        )
        raise typer.Exit(code=4)
    console.print(f"[red]Article wave failed:[/red] {journal_directory / 'result.json'}")
    raise typer.Exit(code=3)


@wave_app.command("reconcile")
def reconcile(
    request_path: Path,
    plan_path: Annotated[Path, typer.Option("--plan")],
    result_path: Annotated[Path, typer.Option("--result")],
    output_path: Annotated[Path, typer.Option("--output", "-o")],
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
    vk_account: Annotated[str, typer.Option("--vk-account")] = VK_ARTICLE_ACCOUNT_ALIAS,
) -> None:
    request = _read_model(request_path, WaveReconciliationRequest)
    plan = _read_model(plan_path, WavePlan)
    result = _read_model(result_path, WaveResult)
    try:
        request.assert_matches(plan, result)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint=str(request_path)) from exc
    if not _article_plan(plan):
        console.print(
            f"[red]Rejected:[/red] no production reconciliation adapter is registered for {request.self_digest}."
        )
        raise typer.Exit(code=3)
    try:
        adapter = VkPostponedArticlePhotoAdapter(
            repository_root=repository_root,
            account_alias=vk_account,
        )
        reconciliation = WaveEngine().reconcile(
            plan=plan,
            result=result,
            request=request,
            adapter=adapter,
            output_path=output_path,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Article reconciliation failed closed:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    console.print(f"[green]Article reconciliation succeeded:[/green] {reconciliation.self_digest} -> {output_path}")


@result_app.command("verify")
def result_verify(
    result_path: Path,
    plan_path: Annotated[Path, typer.Option("--plan")],
) -> None:
    plan = _read_model(plan_path, WavePlan)
    result = _read_model(result_path, WaveResult)
    result.assert_matches(plan)
    console.print(f"[green]Valid wave result:[/green] {result.self_digest}")


@result_app.command("verify-reconciliation")
def reconciliation_result_verify(
    result_path: Path,
    request_path: Annotated[Path, typer.Option("--request")],
) -> None:
    request = _read_model(request_path, WaveReconciliationRequest)
    result = _read_model(result_path, WaveReconciliationResult)
    result.assert_matches(request)
    console.print(f"[green]Valid reconciliation result:[/green] {result.self_digest}")


def schema_documents() -> dict[str, dict[str, object]]:
    return {
        f"{model.model_fields['schema_name'].default}-v1.schema.json": model.model_json_schema()
        for model in WAVE_SCHEMA_MODELS
    }


def load_json_object(path: Path) -> dict[str, object]:
    return read_json_object(path)
