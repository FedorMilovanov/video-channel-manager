# Чарнок — локальные резервные часы Windows (№09–12)

## Назначение

Issue [#997](https://github.com/FedorMilovanov/video-channel-manager/issues/997) фиксирует 6 поздних GitHub `schedule` runs 10/13/17 ноября. Поэтому резервный ручной `workflow_dispatch` из [PR #1021](https://github.com/FedorMilovanov/video-channel-manager/pull/1021) дополнен **независимыми локальными часами**. Это не новый издатель: локальный скрипт вызывает только существующий owner-only GitHub Actions workflow. Он не знает Telegram/Telegraph токенов и не отправляет сообщения напрямую.

| Выпуск | Утверждённый день (МСК) | Резервные запуски |
|---|---|---|
| №09 | 20.11.2026 | 12:05, 12:35, 13:05, 13:35 |
| №10 | 24.11.2026 | 12:05, 12:35, 13:05, 13:35 |
| №11 | 27.11.2026 | 12:05, 12:35, 13:05, 13:35 |
| №12 | 01.12.2026 | 12:05, 12:35, 13:05, 13:35 |

Четыре одноразовых Task Scheduler задания (с повтором каждые 30 минут в течение 95 минут), никаких бесконечных ежедневных cron и никакого catch-up. Установщик `scripts/install_lordchrist_charnock_windows_backup.ps1` сначала проверяет все четыре будущие даты в **read-only** режиме и SHA-256 оригинального скрипта, а затем создаёт задания.

## Контроль и ограничения

`scripts/lordchrist_charnock_external_dispatch.ps1` проверяет текущего GitHub actor `FedorMilovanov`, SHA-256 утверждённого манифеста, SHA Git blob workflow, дату и окно `12:00–13:59 Europe/Moscow`, оригинальную квитанцию в `state/lordchrist-telegram` и отсутствие любого `scheduled_reissue`. `-ProbeAt` разрешён только в режиме без отправки; с `-Dispatch` он запрещён. GitHub workflow сохраняет общий concurrency lock, runtime guards и запрет дублей. №06–08 (пропущенные слоты) и №13 (редакторский HOLD) в этот резерв не входят.

Установка возможна только на Windows с часовой зоной `Russian Standard Time`, `pwsh` 7 и ранее авторизованным `gh api user = FedorMilovanov`.

```powershell
pwsh -NoProfile -File scripts/install_lordchrist_charnock_windows_backup.ps1
pwsh -NoProfile -File scripts/install_lordchrist_charnock_windows_backup.ps1 -Install
Get-ScheduledTask -TaskName 'Lordchrist-Charnock-Reissue-*' |
  Select-Object TaskName, State
```

Первый вызов — только план, без изменений. Второй использует `Register-ScheduledTask`. Существующие одноимённые задания не перезаписываются. Установка копирует скрипт в `%LOCALAPPDATA%\LordchristCharnockScheduler` и удостоверяет SHA-256. Все команды используют уже существующую авторизацию `gh`, не сохраняют новый токен.

**Ограничение надёжности:** установлен тип входа Windows `Interactive` (наименьшие права). Пользователь Windows должен оставаться вошедшим, ПК должен работать/пробуждаться и иметь интернет. `WakeToRun` не гарантирует срабатывания на любом оборудовании. Сам запрос `workflow_dispatch` **не** доказывает публикацию: для закрытия выпуска требуются новая `scheduled_reissue.state=verified` в защищённом реестре и публичный Telegram readback. После завершения серии — проверить все четыре квитанции и удалить только эти четыре задачи.
