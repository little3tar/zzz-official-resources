---
name: zzz-official-resources
description: Download, update-check, repair, and export official Zenless Zone Zero resources from miHoYo Wiki, including calendar wallpapers, wallpaper collection pages, and agent cinema/mindscape images. Use when users ask to download ZZZ official images/videos, check official resource updates, repair missing local files, or export manifests.
metadata:
  short-description: Download and check ZZZ official resources
---

# ZZZ Official Resources

Use this skill for official Zenless Zone Zero resources from miHoYo Wiki:

- Calendar wallpapers
- Wallpaper collection pages under `壁纸合集`
- Agent `意象影画` images

## Required Interaction

Before running a command that writes user files, ask the user to choose:

1. Resource type: `calendar`, `wallpapers`, `cinema`, or `all`
2. Operation: `download`, `check-remote`, `check-local`, `repair`, or `export-manifest`
3. Destination directory when the operation needs one

Do not assume a destination directory. Do not write manifests or CSV files into the user's destination unless the user explicitly asks to export them.

## CLI

Use the bundled script:

```powershell
python scripts/zzz_resources.py list-resources
python scripts/zzz_resources.py check-remote --type all
python scripts/zzz_resources.py check-local --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py download --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py repair --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py export-manifest --type all --dest "C:\path\for\csv"
```

Use the bundled Python runtime if available in Codex Desktop:

```powershell
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\zzz_resources.py ...
```

## Behavior

- Internal manifests live in this skill's `state/` directory:
  - `calendar_manifest.csv`
  - `wallpapers_manifest.csv`
  - `cinema_manifest.csv`
  - `last_check_report.csv`
- `download` refreshes the internal manifest and writes resources to the confirmed destination.
- `check-remote` compares the current official site against the internal manifest and writes only `state/last_check_report.csv`.
- `check-local` checks the confirmed destination for missing or zero-byte files.
- `repair` only downloads missing or zero-byte files.
- `export-manifest` copies internal manifests to the user-confirmed destination.
- Never delete user files automatically. Report unknown extra files or removed remote resources instead.

## Naming

- Calendar wallpapers: `壁纸合集/月历壁纸合集/<year>PC版壁纸收录/<month>月.ext` and `壁纸合集/月历壁纸合集/<year>手机版壁纸收录/<month>月.ext`.
- Wallpaper collections: `壁纸合集/<collection>/<web group>/...`; single-group collections are flattened.
- Agent cinema images: `意象影画/<agent>/影画展示1.ext`, `影画展示2.ext`, `影画展示3.ext`.

## Safety Notes

Writing outside the workspace or into OneDrive may require escalation. Ask for confirmation at action time when the tool requires it. CSV export is user-visible output and must only happen after the user requests it.

## Known Pitfalls / Troubleshooting

- Do not parse the visible HTML page for resource data. The page is mostly a Nuxt shell; use the `entry_page` API for content.
- Do not use `entry_page_v2` as the default detail API. It may return HTTP 403 in this environment.
- Always send `X-Rpc-Wiki_app: zzz` when requesting `hoyowiki/zzz/wapi/entry_page`.
- For channel pages, `home/map` may only include the homepage preview list. Use `home/content/list?channel_id=<id>&page_num=1&page_size=100` for complete channel item lists, especially the agent channel `43`.
- For wallpaper collection grouping, do not rely on `module.name`; it is often empty. Use `template_layout.tab[].module_group[].name` and map those group modules back to `page.modules[].id`.
- Static images usually come from `map_desc` component data: `data.list[].image` with `data.list[].tab_name`.
- Dynamic wallpaper MP4 files are embedded in rich text as `data-video-url` or `<video src=...>`, not in `map_desc.image`.
- Agent cinema files are the three image tabs named `影画展示1`, `影画展示2`, and `影画展示3`. Preview/unreleased agents may have no cinema images; treat that as normal, not as a failure.
- Calendar wallpaper modules expose group names such as `2026PC版壁纸收录` and `2026手机版壁纸收录`. Infer the year and PC/mobile suffix from those group names, and infer the month from tab names.
- Manifests and check reports must stay in `state/` by default. Only run `export-manifest` after the user explicitly asks to inspect or receive CSV files.
- Never delete user files automatically. If remote resources disappear, local files are extra, or old empty folders remain, report them and ask before deletion.
