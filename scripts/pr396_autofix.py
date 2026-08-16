from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one replacement in {path}, found {count}: {old!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


bootstrap = "src/video_channel_manager/milovi_telegram_bootstrap.py"
replace_once(
    bootstrap,
    "from video_channel_manager.telegram_multichannel_release import GenericReleaseItem, GenericReleaseQueue, save_release",
    "from video_channel_manager.telegram_multichannel_release import (\n"
    "    GenericProviderPayload,\n"
    "    GenericReleaseItem,\n"
    "    GenericReleaseQueue,\n"
    "    save_release,\n"
    ")",
)
replace_once(
    bootstrap,
    '        if rollout_item["operation"] == "sendPhoto":\n',
    '        payload: GenericProviderPayload\n        if rollout_item["operation"] == "sendPhoto":\n',
)
replace_once(
    bootstrap,
    "        from PIL import Image\n",
    "        from PIL import Image  # type: ignore[import-not-found]\n",
)

replace_once(
    "tests/test_http_client_inventory.py",
    '        "src/video_channel_manager/telegram_multichannel_transport.py": 3,',
    '        "src/video_channel_manager/telegram_multichannel_transport.py": 4,',
)

multichannel_test = "tests/test_telegram_multichannel.py"
replace_once(
    multichannel_test,
    '''        elif method == "getChatAdministrators":
            assert payload == {"chat_id": -1001234567890, "return_bots": True}
            result = [
                {
                    "status": "administrator",
                    "can_post_messages": True,
                    "user": {"id": 42, "is_bot": True, "username": "svodka_test_bot"},
                }
            ]
''',
    '''        elif method == "getChatMember":
            assert payload == {"chat_id": -1001234567890, "user_id": 42}
            result = {
                "status": "administrator",
                "can_post_messages": True,
                "user": {"id": 42, "is_bot": True, "username": "svodka_test_bot"},
            }
''',
)
replace_once(
    multichannel_test,
    '    assert calls == ["getMe", "getChat", "getChat", "getChatAdministrators"]',
    '    assert calls == ["getMe", "getChat", "getChat", "getChatMember"]',
)
