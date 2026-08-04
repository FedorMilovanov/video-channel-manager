# Agent instructions for Fedor's Windows handoffs

These instructions complement the repository-root `AGENTS.md`. The project identity, mutation safety, provider-write, and operational-evidence rules in `AGENTS.md` remain authoritative.

## Fixed user paths

Unless Fedor explicitly gives a different location, use these exact local paths in every user-facing Windows command:

```text
Repository: C:\Users\Fedor\Projects\video-channel-manager
Downloads and handoff files: C:\Users\Fedor\Downloads
```

Fedor saves downloaded ChatGPT artifacts in `C:\Users\Fedor\Downloads`. Do not assume that a downloaded ZIP, TXT, HTML, JSON, or PowerShell script is inside the repository or the current PowerShell directory.

## Mandatory PowerShell construction

Every copy-paste command block must be self-contained. Define all paths in the same block; never depend on a variable created in an earlier assistant message or terminal session.

Start with explicit variables such as:

```powershell
$Repo = "C:\Users\Fedor\Projects\video-channel-manager"
$Downloads = "C:\Users\Fedor\Downloads"
$Package = Join-Path $Downloads "EXACT-DOWNLOADED-OR-EXTRACTED-NAME"
```

Required rules:

1. Use absolute paths or paths derived from `$Repo` and `$Downloads`.
2. Use `-LiteralPath` when testing, reading, copying, extracting, or invoking known files.
3. Validate every required file with `Test-Path -LiteralPath ... -PathType Leaf` before invocation.
4. Never issue `\.\script.ps1` unless the same command block first changes to the exact directory containing that script and verifies it. Prefer invoking the exact full path.
5. Never use an undefined variable such as `$wave`, `$package`, `$zip`, or `$out`.
6. Do not rely on the prompt's current directory. Commands must still work when PowerShell is currently in `C:\Users\Fedor\Projects\video-channel-manager`.
7. When the user has downloaded a ZIP, include the exact `Expand-Archive` step, the exact extraction directory, and the exact resulting package root.
8. If an artifact filename is already known, write that exact filename instead of a placeholder.
9. If filename discovery is unavoidable, require exactly one match and fail on zero or multiple matches. Do not silently select an arbitrary file.
10. Use `$PSScriptRoot` inside delivered scripts so that sibling files resolve from the script's own folder.

Example invocation from any current directory:

```powershell
$Downloads = "C:\Users\Fedor\Downloads"
$Package = Join-Path $Downloads "legendary-poet-vk-article-wave-202608"
$Script = Join-Path $Package "ОТКРЫТЬ-ПОСТЫ.ps1"

if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
    throw "Script not found: $Script"
}

powershell.exe -ExecutionPolicy Bypass -File $Script
```

## Downloaded ZIP handoff pattern

A handoff containing a ZIP must provide a complete extraction-and-run block similar to this:

```powershell
$Downloads = "C:\Users\Fedor\Downloads"
$Zip = Join-Path $Downloads "EXACT-PACKAGE.zip"
$ExtractRoot = Join-Path $Downloads "EXACT-PACKAGE-EXTRACTED"

if (-not (Test-Path -LiteralPath $Zip -PathType Leaf)) {
    throw "Downloaded ZIP not found: $Zip"
}

if (Test-Path -LiteralPath $ExtractRoot) {
    Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
}

Expand-Archive -LiteralPath $Zip -DestinationPath $ExtractRoot -Force

$Package = Join-Path $ExtractRoot "EXACT-INNER-FOLDER"
$Script = Join-Path $Package "EXACT-SCRIPT.ps1"

if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
    throw "Expected script not found after extraction: $Script"
}

powershell.exe -ExecutionPolicy Bypass -File $Script
```

The exact ZIP filename, inner folder, and script filename must be substituted before showing the command to the user.

## Windows text encoding

For user-facing Windows artifacts:

- write `.ps1` and human-readable `.txt` files as UTF-8 with BOM;
- use explicit `<meta charset="utf-8">` in HTML;
- keep JSON as valid UTF-8;
- avoid relying on the editor's automatic encoding detection;
- when opening a file, invoke the exact file path, not whichever similarly named tab or document is already open.

A handoff should preferably include a browser-readable HTML preview as well as a Windows-safe UTF-8-with-BOM TXT version when Russian text is important.

## Handoff response checklist

Before sending commands to Fedor, verify that the response includes:

1. the exact artifact download link;
2. the exact filename expected in `C:\Users\Fedor\Downloads`;
3. one complete copy-paste PowerShell block that defines all variables;
4. extraction instructions when the artifact is a ZIP;
5. `Test-Path` validation before execution;
6. the exact expected output or success marker;
7. an explicit statement whether the command is read-only or can write to a provider;
8. the exact project/community/owner confirmation for any VK operation.

## Prohibited handoff patterns

Do not give Fedor commands that:

- assume downloaded files are in the repository;
- depend on an earlier `$wave` or similar variable;
- invoke `\.\ОТКРЫТЬ-ПОСТЫ.ps1` while PowerShell is in the repository and the script is in Downloads;
- say "open all texts" but point to a different or ambiguous filename;
- omit extraction and then invoke a script that exists only inside a ZIP;
- use mojibake-prone plain UTF-8 text without BOM for Russian Windows handoffs;
- instruct the user to rerun a retired provider-write executor merely because the local file path is convenient.
