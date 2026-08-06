from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from video_channel_manager.config import get_settings
from video_channel_manager.platforms.vk.postponed_text_edit import (
    VkPostponedTextEditError,
    build_vk_postponed_text_edit_plan,
    execute_vk_postponed_text_edit_plan,
    load_vk_postponed_text_edit_plan,
    load_vk_postponed_text_edit_request,
    reconcile_vk_postponed_text_edit_plan,
    write_vk_postponed_text_document,
)
from video_channel_manager.platforms.vk.store import VkAccountNotFoundError, VkTokenStore
from video_channel_manager.platforms.vk.wall import VkWallWriter
from video_channel_manager.platforms.vk.writer import VkWriteError

app = typer.Typer(
    no_args_is_help=True,
    help="Plan, reconcile, and safely apply exact text edits to existing postponed VK wall posts.",
)
console = Console()


def _writer(account: str) -> VkWallWriter:
    settings = get_settings()
    store = VkTokenStore(settings.data_dir)
    return VkWallWriter(
        token_store=store,
        account_alias=account,
        api_version=settings.vk_api_version,
    )


def _print_reconciliation(payload: dict[str, object]) -> None:
    table = Table(title="VK postponed text edit reconciliation")
    table.add_column("Metric")
    table.add_column("Value")
    for key in ("status", "postponed_count", "operation_count", "before", "after", "conflict", "plan_sha256"):
        table.add_row(key, str(payload.get(key)))
    console.print(table)


@app.command("plan")
def plan_command(
    request_path: Annotated[Path, typer.Argument(help="Reviewed JSON request with exact post IDs and line rules")],
    output_path: Annotated[Path, typer.Option("--output", "-o", help="Immutable plan JSON output")],
    account: Annotated[str, typer.Option("--account", "-a", help="Local VK credential alias")] = "legendary-poet",
    max_posts_per_surface: Annotated[int, typer.Option("--max-posts-per-surface", min=1)] = 10000,
) -> None:
    """Build a mutation-free exact-ID plan from the current postponed surface."""

    try:
        request = load_vk_postponed_text_edit_request(request_path)
        with _writer(account) as writer:
            plan = build_vk_postponed_text_edit_plan(
                writer,
                request,
                max_posts_per_surface=max_posts_per_surface,
            )
        write_vk_postponed_text_document(output_path, plan)
    except (
        VkAccountNotFoundError,
        VkPostponedTextEditError,
        VkWriteError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        console.print(f"[red]VK postponed-text plan failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"[green]Plan written:[/green] {output_path}")
    console.print(f"Operations: {plan['operation_count']}")
    console.print(f"Postponed baseline: {plan['expected_postponed_count']}")
    console.print(f"Plan SHA-256: {plan['plan_sha256']}")
    console.print("VK was read only; no wall post was changed.")


@app.command("reconcile")
def reconcile_command(
    plan_path: Annotated[Path, typer.Argument(help="Immutable postponed-text edit plan JSON")],
    output_path: Annotated[Path, typer.Option("--output", "-o", help="Reconciliation JSON output")],
    account: Annotated[str, typer.Option("--account", "-a")] = "legendary-poet",
    max_posts_per_surface: Annotated[int, typer.Option("--max-posts-per-surface", min=1)] = 10000,
) -> None:
    """Classify every planned post as exact-before, exact-after, or conflict without writing VK."""

    try:
        plan = load_vk_postponed_text_edit_plan(plan_path)
        with _writer(account) as writer:
            payload = reconcile_vk_postponed_text_edit_plan(
                writer,
                plan,
                max_posts_per_surface=max_posts_per_surface,
            )
        write_vk_postponed_text_document(output_path, payload)
    except (
        VkAccountNotFoundError,
        VkPostponedTextEditError,
        VkWriteError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        console.print(f"[red]VK postponed-text reconciliation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    _print_reconciliation(payload)
    console.print(f"Result: {output_path}")
    if payload["status"] != "ready":
        raise typer.Exit(code=4)


@app.command("apply")
def apply_command(
    plan_path: Annotated[Path, typer.Argument(help="Immutable postponed-text edit plan JSON")],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Durable journals and result directory")],
    confirm_plan_sha256: Annotated[
        str,
        typer.Option("--confirm-plan-sha256", help="Exact plan digest printed by the plan command"),
    ],
    account: Annotated[str, typer.Option("--account", "-a")] = "legendary-poet",
    enable_provider_writes: Annotated[
        bool,
        typer.Option("--enable-provider-writes", help="Required explicit wall.edit authority"),
    ] = False,
    minimum_future_seconds: Annotated[int, typer.Option("--minimum-future-seconds", min=0)] = 600,
    inter_operation_delay_seconds: Annotated[
        float,
        typer.Option("--inter-operation-delay-seconds", min=0.0),
    ] = 25.0,
    postflight_delay_seconds: Annotated[
        float,
        typer.Option("--postflight-delay-seconds", min=0.0),
    ] = 3.0,
    transient_retry_delay_seconds: Annotated[
        float,
        typer.Option("--transient-retry-delay-seconds", min=0.0),
    ] = 90.0,
    max_transient_retries: Annotated[int, typer.Option("--max-transient-retries", min=0)] = 1,
    max_posts_per_surface: Annotated[int, typer.Option("--max-posts-per-surface", min=1)] = 10000,
) -> None:
    """Apply or resume a confirmed plan; already-after posts are skipped."""

    try:
        plan = load_vk_postponed_text_edit_plan(plan_path)
        with _writer(account) as writer:
            result = execute_vk_postponed_text_edit_plan(
                writer,
                plan,
                output_dir=output_dir,
                confirm_plan_sha256=confirm_plan_sha256,
                enable_provider_writes=enable_provider_writes,
                minimum_future_seconds=minimum_future_seconds,
                inter_operation_delay_seconds=inter_operation_delay_seconds,
                postflight_delay_seconds=postflight_delay_seconds,
                transient_retry_delay_seconds=transient_retry_delay_seconds,
                max_transient_retries=max_transient_retries,
                max_posts_per_surface=max_posts_per_surface,
            )
    except (
        VkAccountNotFoundError,
        VkPostponedTextEditError,
        VkWriteError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        console.print(f"[red]VK postponed-text apply failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    table = Table(title="VK postponed text edit result")
    table.add_column("Metric")
    table.add_column("Value")
    for key in (
        "status",
        "operation_count",
        "already_after_before_apply",
        "newly_verified",
        "total_verified",
        "non_target_postponed_unchanged",
        "postponed_count_before",
        "postponed_count_after",
        "stopped_post_id",
        "plan_sha256",
    ):
        if key in result:
            table.add_row(key, str(result[key]))
    console.print(table)
    console.print(f"Result: {output_dir / 'result.json'}")
    if result["status"] != "succeeded":
        raise typer.Exit(code=4)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
