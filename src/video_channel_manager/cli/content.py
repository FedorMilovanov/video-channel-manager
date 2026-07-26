"""Public editorial CLI assembled from focused command modules."""

import typer

from video_channel_manager.cli._content_commands import (
    plan_adapt_vk_catalog_command,
    plan_validate_command,
    preview_command,
    validate_command,
)
from video_channel_manager.cli._content_plan_cli import (
    plan_build_command,
    plan_preflight_command,
)

content_app = typer.Typer(
    no_args_is_help=True,
    help="Canonical editorial records, platform previews, and signed plans.",
)
content_plan_app = typer.Typer(
    no_args_is_help=True,
    help="Build and preflight signed editorial content plans.",
)
content_app.add_typer(content_plan_app, name="plan")
content_app.command("validate")(validate_command)
content_app.command("preview")(preview_command)
content_plan_app.command("build")(plan_build_command)
content_plan_app.command("validate")(plan_validate_command)
content_plan_app.command("preflight")(plan_preflight_command)
content_plan_app.command("adapt-vk-catalog")(plan_adapt_vk_catalog_command)

__all__ = ["content_app"]
