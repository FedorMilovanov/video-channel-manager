# VK catalog editorial policy

Версия политики: `video-manager.vk-catalog-policy` / `1`  
Файл: `content/policies/vk-catalog-policy.json`

## Зачем отдельная политика

YouTube playlists являются исходным редакционным сигналом, но не должны копироваться в VK без проверки. Текущий catalog builder:

- создаёт альбом только при наличии хотя бы одного подтверждённо сопоставленного VK-видео;
- не создаёт пустые альбомы для ещё не перенесённых авторов;
- применяет только явно перечисленные title overrides;
- не переименовывает существующие VK-альбомы автоматически;
- фиксирует skipped/excluded collections в `review_only`;
- включает полный policy payload и `catalog_policy_sha256` в self-validating plan.

## Текущие нормализованные названия

```text
Поющие Поэты                 → Поющие поэты
Эксперименты AI              → AI-эксперименты
Чёрный Человек — Сергей Есенин → Чёрный человек — Сергей Есенин
```

Авторские альбомы сохраняют обычные имена: `Сергей Есенин`, `Александр Блок`, `Александр Пушкин` и так далее.

`Поющие поэты` намеренно не переименован в `Полные версии`: исходный плейлист содержит смешанный материал, а точная классификация Shorts требует длительности и геометрии.

## Авторитетная команда построения плана

Эта команда заменяет шаг 3 первоначального runbook:

```powershell
python .\scripts\build_vk_catalog_plan.py `
    "$($yt.FullName)" `
    "$($vk.FullName)" `
    --mapping-json .\content\mappings\youtube-vk-reviewed-20260725.json `
    --policy-json .\content\policies\vk-catalog-policy.json `
    --output "$repo\data\reports\vk-catalog-plan.json" `
    --report "$repo\data\reports\vk-catalog-plan.md"
```

Перед dry-run проверить в Markdown report:

- `Catalog policy` содержит SHA-256;
- `Albums to create` не включает пустые авторские альбомы;
- `Applied catalog policy` перечисляет только ожидаемые title overrides;
- `Review only` содержит пропущенные коллекции и неоднозначности;
- каждый planned album имеет хотя бы одно planned или already-existing membership.

## Изменение политики

Не редактировать generated plan вручную. Изменить `content/policies/vk-catalog-policy.json`, повторно построить plan и заново просмотреть Markdown report. Любое изменение политики меняет `catalog_policy_sha256` и итоговый `plan_sha256`.
