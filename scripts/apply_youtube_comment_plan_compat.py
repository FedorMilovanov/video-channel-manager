from __future__ import annotations

import sys
from typing import NoReturn, TextIO


def _configure_utf8_stream(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def _run() -> NoReturn:
    """Preserve the operational entrypoint used by existing Windows runbooks.

    The moderation-state reads, context-aware exact reads, and bounded eventual
    verification formerly installed here by monkeypatch now live permanently in
    YouTubeCommentWriter. Keeping this wrapper avoids breaking saved commands,
    signed-wave launchers, and recovery instructions.
    """

    _configure_utf8_stream(sys.stdout)
    _configure_utf8_stream(sys.stderr)

    from apply_youtube_comment_plan import main

    raise SystemExit(main())


if __name__ == "__main__":
    _run()
