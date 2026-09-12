from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DailyItemStatus = Literal["ready", "published", "rights_review"]

PUBLISHED_SOURCE_IDS = frozenset({"T6WIgGaZm74", "0C1-2tk9aQg"})
RIGHTS_REVIEW: dict[str, str] = {
    "Yu0iV0fDsPQ": "modern song cover: Я свободен / Маврин",
    "g9bW6upeQCg": "modern song adaptation: КИНО / Спокойная ночь",
    "7N-DEjLDZ3I": "off-brand game-content Short: Heroes 3",
    "9nD37a7hKQ8": "modern song cover: Алиса / Шабаш",
    "gavdyL0QWJU": "modern copyrighted song adaptation: Расскажи, Снегурочка",
    "TDbW__q3hYk": "modern song cover: Виктор Цой",
}

AUTHOR_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Сергей Есенин", ("сергей есенин", "sergey esenin", "sergei esenin", "есенин")),
    ("Александр Пушкин", ("а. с. пушкин", "александр пушкин", "пушкин")),
    ("Михаил Лермонтов", ("м. ю. лермонтов", "михаил лермонтов", "лермонтов")),
    ("Владимир Маяковский", ("владимир маяковский", "маяковский")),
    ("Александр Блок", ("александр блок", "блока", "блок")),
    ("Анна Ахматова", ("анна ахматова", "ахматова")),
    ("Николай Некрасов", ("николай некрасов", "некрасов")),
    ("Валерий Брюсов", ("валерий брюсов", "брюсов")),
    ("Афанасий Фет", ("афанасий фет", "фет")),
    ("Алексей Толстой", ("а. к. толстой", "алексей толстой")),
    ("Константин Симонов", ("константин симонов", "симонов")),
    ("Борис Пастернак", ("борис пастернак", "пастернак")),
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InstagramDailyQueueItem(FrozenModel):
    source_id: str = Field(min_length=1)
    source_url: str
    source_title: str = Field(min_length=1)
    author: str | None = None
    duration_seconds: float = Field(gt=0, le=180)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source_upload_date: str = Field(pattern=r"^\d{8}$")
    source_view_count: int = Field(ge=0)
    source_like_count: int = Field(ge=0)
    priority_score: float
    status: DailyItemStatus
    hold_reason: str | None = None
    scheduled_at: datetime | None = None
    publication_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    caption: str = Field(max_length=2200)
    hashtags: tuple[str, ...] = Field(max_length=5)

    @model_validator(mode="after")
    def validate_item(self) -> InstagramDailyQueueItem:
        if self.width >= self.height:
            raise ValueError("daily Reel source must be portrait")
        if self.status == "ready" and self.scheduled_at is None:
            raise ValueError("ready item requires scheduled_at")
        if self.status != "ready" and self.scheduled_at is not None:
            raise ValueError("non-ready item must not have scheduled_at")
        if self.status == "rights_review" and not self.hold_reason:
            raise ValueError("rights_review item requires hold_reason")
        if self.scheduled_at is not None and self.scheduled_at.tzinfo is None:
            raise ValueError("scheduled_at must be timezone-aware")
        if len(self.hashtags) != len(set(self.hashtags)):
            raise ValueError("hashtags must be unique")
        return self


class InstagramDailyQueue(FrozenModel):
    schema_name: Literal["video-manager.instagram-daily-reels-queue"] = (
        "video-manager.instagram-daily-reels-queue"
    )
    schema_version: Literal[1] = 1
    status: Literal["provider-inert"] = "provider-inert"
    provider_writes_authorized: Literal[False] = False
    project_key: Literal["legendary-poet"] = "legendary-poet"
    account_id: str
    youtube_channel_id: str
    timezone: str
    source_snapshot_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    start_at: datetime
    item_count: int
    ready_count: int
    published_count: int
    rights_review_count: int
    items: tuple[InstagramDailyQueueItem, ...]

    @model_validator(mode="after")
    def validate_queue(self) -> InstagramDailyQueue:
        if self.start_at.tzinfo is None:
            raise ValueError("start_at must be timezone-aware")
        if len(self.items) != self.item_count:
            raise ValueError("item_count differs from actual items")
        statuses = [item.status for item in self.items]
        if statuses.count("ready") != self.ready_count:
            raise ValueError("ready_count differs from actual items")
        if statuses.count("published") != self.published_count:
            raise ValueError("published_count differs from actual items")
        if statuses.count("rights_review") != self.rights_review_count:
            raise ValueError("rights_review_count differs from actual items")
        source_ids = [item.source_id for item in self.items]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique")
        keys = [item.publication_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("publication keys must be unique")
        schedule = sorted(
            item.scheduled_at for item in self.items if item.status == "ready"
        )
        if len(schedule) != len(set(schedule)):
            raise ValueError("ready schedule must use unique slots")
        for previous, current in zip(schedule, schedule[1:], strict=False):
            if current - previous != timedelta(days=1):
                raise ValueError("ready schedule must be one slot per day")
        return self


def clean_title(value: str) -> str:
    value = value.replace("\u2068", "").replace("\u2069", "").replace("\u200b", "")
    value = re.sub(r"\s*@TheLegendaryPoet\b", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\s*#(?:Shorts|TheLegendaryPoet|TheEpicPoet)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip(" -")


def detect_author(title: str, tags: list[str]) -> str | None:
    haystack = (title + " " + " ".join(tags)).casefold()
    for canonical, aliases in AUTHOR_ALIASES:
        if any(alias in haystack for alias in aliases):
            return canonical
    return None


def hashtags_for(title: str, author: str | None) -> tuple[str, ...]:
    is_ru = bool(re.search(r"[А-Яа-яЁё]", title))
    tags: list[str] = []
    if author:
        compact = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "", author)
        if compact:
            tags.append(f"#{compact}")
    tags.extend(["#РусскаяПоэзия", "#Поэзия"] if is_ru else ["#RussianPoetry", "#Poetry"])
    folded = title.casefold()
    if "рок" in folded:
        tags.append("#РокВерсия")
    elif "dj" in folded or "регги" in folded:
        tags.append("#ПоэзияПодМузыку")
    else:
        tags.append("#СтихиПодМузыку" if is_ru else "#PoetryMusic")
    tags.append("#TheLegendaryPoet")
    return tuple(dict.fromkeys(tags))[:5]


def caption_for(
    source_id: str,
    title: str,
    author: str | None,
    hashtags: tuple[str, ...],
) -> str:
    is_ru = bool(re.search(r"[А-Яа-яЁё]", title))
    folded = title.casefold()
    if is_ru:
        if "рок" in folded:
            context = (
                "Русская поэзия в рок-прочтении: классический текст, музыка "
                "и кинематографичный визуал."
            )
        elif "dj" in folded or "регги" in folded:
            context = (
                "Классическая поэзия встречается с современным музыкальным "
                "звучанием и визуальным экспериментом."
            )
        elif author:
            context = (
                f"{author}: классическая поэзия в музыкальном и визуальном "
                "прочтении The Legendary Poet."
            )
        else:
            context = "Поэзия в музыкальном и визуальном прочтении The Legendary Poet."
        ctas = (
            "Сохрани Reel, чтобы вернуться к этим строкам, и отправь его тому, кому они могут откликнуться.",
            "Какая строка здесь цепляет сильнее всего? Сохрани и поделись Reel с тем, кто любит поэзию.",
            "Если такое прочтение тебе близко — сохрани Reel и отправь его человеку, которому стоит это услышать.",
            "Вернись к этому стихотворению позже: сохрани Reel и поделись им с любителем русской поэзии.",
        )
    else:
        context = (
            "Russian poetry in a new musical and cinematic interpretation "
            "by The Legendary Poet."
        )
        ctas = (
            "Save this Reel for another listen and send it to someone who loves poetry.",
            "Which line stays with you? Save the Reel and share it with a poetry lover.",
            "If this interpretation resonates, save the Reel and send it to someone who should hear it.",
            "Come back to these lines later: save this Reel and share it with someone who loves Russian poetry.",
        )
    variant = int(hashlib.sha256(source_id.encode()).hexdigest()[:8], 16) % len(ctas)
    return f"{title}\n\n{context}\n\n{ctas[variant]}\n\n{' '.join(hashtags)}"


def priority_score(
    view_count: int,
    like_count: int,
    upload_date: str,
    newest_date: str,
) -> float:
    views = max(view_count, 0)
    likes = max(like_count, 0)
    engagement = likes / views if views else 0.0
    newest = datetime.strptime(newest_date, "%Y%m%d").date()
    uploaded = datetime.strptime(upload_date, "%Y%m%d").date()
    age_days = max((newest - uploaded).days, 0)
    recency = max(0.0, 1.0 - age_days / 365.0)
    return round(
        math.log1p(views) + min(engagement, 0.25) * 5.0 + recency * 0.5,
        6,
    )


def diversify(items: list[dict[str, object]]) -> list[dict[str, object]]:
    remaining = sorted(
        items,
        key=lambda item: (-float(item["priority_score"]), str(item["source_id"])),
    )
    result: list[dict[str, object]] = []
    last_author: str | None = None
    while remaining:
        index = 0
        if last_author:
            alternate = next(
                (i for i, item in enumerate(remaining) if item.get("author") != last_author),
                None,
            )
            if alternate is not None:
                index = alternate
        chosen = remaining.pop(index)
        result.append(chosen)
        author = chosen.get("author")
        last_author = author if isinstance(author, str) else None
    return result


def build_legendary_poet_daily_queue(
    snapshot_path: Path,
    *,
    account_id: str,
    start_at: datetime,
    timezone_name: str = "Europe/Moscow",
) -> InstagramDailyQueue:
    raw = snapshot_path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if payload.get("schema_name") != "video-manager.legendary-poet-youtube-shorts-snapshot":
        raise ValueError("unexpected Shorts snapshot schema")
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Shorts snapshot has no items")

    newest_date = max(str(row["upload_date"]) for row in rows)
    staged: list[dict[str, object]] = []
    for row in rows:
        source_id = str(row["id"])
        title = clean_title(str(row["title"]))
        tags = [str(tag) for tag in (row.get("tags") or [])]
        author = detect_author(title, tags)
        views = int(row.get("view_count") or 0)
        likes = int(row.get("like_count") or 0)
        staged.append(
            {
                "source_id": source_id,
                "source_url": f"https://www.youtube.com/shorts/{source_id}",
                "source_title": title,
                "author": author,
                "duration_seconds": float(row["duration"]),
                "width": int(row["width"]),
                "height": int(row["height"]),
                "source_upload_date": str(row["upload_date"]),
                "source_view_count": views,
                "source_like_count": likes,
                "priority_score": priority_score(
                    views,
                    likes,
                    str(row["upload_date"]),
                    newest_date,
                ),
            }
        )

    blocked_ids = PUBLISHED_SOURCE_IDS | frozenset(RIGHTS_REVIEW)
    ready = diversify(
        [item for item in staged if str(item["source_id"]) not in blocked_ids]
    )
    ready_order = {
        str(item["source_id"]): index for index, item in enumerate(ready)
    }

    items: list[InstagramDailyQueueItem] = []
    for item in staged:
        source_id = str(item["source_id"])
        if source_id in PUBLISHED_SOURCE_IDS:
            status: DailyItemStatus = "published"
            scheduled_at = None
            hold_reason = None
        elif source_id in RIGHTS_REVIEW:
            status = "rights_review"
            scheduled_at = None
            hold_reason = RIGHTS_REVIEW[source_id]
        else:
            status = "ready"
            scheduled_at = start_at + timedelta(days=ready_order[source_id])
            hold_reason = None

        author = item["author"] if isinstance(item["author"], str) else None
        hashtags = hashtags_for(str(item["source_title"]), author)
        caption = caption_for(
            source_id,
            str(item["source_title"]),
            author,
            hashtags,
        )
        items.append(
            InstagramDailyQueueItem(
                **item,
                status=status,
                hold_reason=hold_reason,
                scheduled_at=scheduled_at,
                publication_key=f"legendary-poet-yt-{source_id}-daily-v1",
                caption=caption,
                hashtags=hashtags,
            )
        )

    statuses = [item.status for item in items]
    return InstagramDailyQueue(
        account_id=account_id,
        youtube_channel_id=str(payload["channel_id"]),
        timezone=timezone_name,
        source_snapshot_sha256=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        start_at=start_at,
        item_count=len(items),
        ready_count=statuses.count("ready"),
        published_count=statuses.count("published"),
        rights_review_count=statuses.count("rights_review"),
        items=tuple(items),
    )


def queue_sha256(queue: InstagramDailyQueue) -> str:
    encoded = json.dumps(
        queue.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
