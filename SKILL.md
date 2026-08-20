---
name: zzz-official-resources
description: Download, update-check, repair, and export official Zenless Zone Zero resources from miHoYo Wiki, including wallpaper collections and agent profiles (cinema images, character display animations, media materials, goodwill wallpaper videos). Use when users ask to download ZZZ official images/videos, check official resource updates, repair missing local files, or export manifests.
metadata:
  short-description: Download and check ZZZ official resources
---

# ZZZ Official Resources

Use this skill for official Zenless Zone Zero resources from miHoYo Wiki:

- Calendar wallpapers
- Wallpaper collection pages under `壁纸合集`
- Agent profiles under `代理档案`:
  - `意象影画` mindscape/cinema images
  - `角色展示` character display animations (GIF) and stills
  - `媒体物料` media materials (character cards, unreleased images)
  - `好感壁纸` goodwill wallpaper videos (MP4)
- Agent videos from channel 73 under `代理档案/<agent>/`:
  - `不可售影像.mp4` non-sale character videos (highest quality: 2K > 1080P > 720P > 480P)
  - `代理人档案.mp4` agent archive videos

## Required Interaction

Before running a command that writes user files, ask the user to choose:

1. Resource type: `wallpapers`, `cinema`, `goodwill`, `agent_videos`, or `all`
2. Operation: `download`, `check-remote`, `check-local`, `repair`, or `export-manifest`
3. Destination directory when the operation needs one

Do not assume a destination directory. Do not write manifests or CSV files into the user's destination unless the user explicitly asks to export them.

### Full local update audit

When a user asks whether **local files need updating**, whether the archive is complete, or reports that an official page has files absent locally, treat this as a two-part audit after confirming the resource type and destination:

1. Run `check-remote` to compare the current official resource inventory with the local manifests. This finds new, removed, renamed, or changed official records.
2. Then run `check-local` to verify that every record in the refreshed manifests exists locally and is non-zero-byte. This finds files that are known to the manifest but were never downloaded, were deleted, or are damaged.

Do not describe `check-remote` alone as proof that the local archive is complete. `unchanged` means only that the official inventory matches the manifest; it does not mean every manifest file is present on disk. Report the remote-comparison result and the local-integrity result separately. Both commands write `<dest>/.manifests/last_check_report.csv`, so the second (`check-local`) report replaces the first; preserve the first command's terminal summary in the user-facing result rather than exporting an extra report unless the user asks.

### Proactive missing-file handling

When an audit finds missing or zero-byte local files:

1. Report the total count and group the results by resource type and agent/collection when practical.
2. List a short sample of missing paths (for large result sets, show at most 10 representative files) and point to `last_check_report.csv` for the complete list.
3. Ask the user whether to download the missing files; do not run `download` or `repair` before the user confirms.
4. If the user confirms, confirm the resource type and destination from the audit context, then run `repair` for missing/zero-byte files. Use `download` when the user explicitly requests a full refresh.
5. After downloading, run `check-local` again and report the final missing/ok counts.

If no files are missing or zero-byte, state that the local integrity check is complete and do not ask about a download.

## CLI

Run the package from the skill root via the project virtual environment:

```powershell
.venv\Scripts\python.exe -m scripts.zzz_resources list-resources --dest "C:\path\to\resources"
.venv\Scripts\python.exe -m scripts.zzz_resources check-remote --type all --dest "C:\path\to\resources"
.venv\Scripts\python.exe -m scripts.zzz_resources check-local --type all --dest "C:\path\to\resources"
.venv\Scripts\python.exe -m scripts.zzz_resources download --type all --dest "C:\path\to\resources"
.venv\Scripts\python.exe -m scripts.zzz_resources repair --type all --dest "C:\path\to\resources"
.venv\Scripts\python.exe -m scripts.zzz_resources export-manifest --type all --manifest-src "C:\path\to\resources" --dest "C:\path\for\csv"
```

## Behavior

- Manifests and reports are stored in `<dest>/.manifests/`:
  - `wallpapers_manifest.csv`
  - `cinema_manifest.csv`
  - `goodwill_manifest.csv`
  - `agent_videos_manifest.csv`
  - `last_check_report.csv`
- `download` refreshes the manifest and writes resources to the confirmed destination.
- `check-remote` compares the current official site against the existing manifest and writes the check report.
- `check-remote` does **not** test whether the corresponding local files exist; follow it with `check-local` for a complete local update audit.
- Remote comparison separates stable resource identity from revision metadata. Report statuses are `new`, `removed`, `renamed`, `changed`, `resolved`, `unknown`, and `unchanged`.
- Expiring video authorization parameters do not count as changes. A transient API failure reports `unknown` and preserves the last usable manifest URL instead of overwriting it with an empty value.
- Before remote comparison, download, or repair, normalize official `.gif` records to an existing local `.webp` file when the CDN payload was previously detected as WebP.
- `check-local` checks the confirmed destination for missing or zero-byte files.
- `repair` only downloads missing or zero-byte files.
- `export-manifest` copies manifests from `--manifest-src` to `--dest` (separate from the project manifests).
- Never delete user files automatically. Report unknown extra files or removed remote resources instead.

## Naming

- Calendar wallpapers: `壁纸合集/月历壁纸合集/<year>PC版壁纸收录/<month>月.ext` and `壁纸合集/月历壁纸合集/<year>手机版壁纸收录/<month>月.ext`.
- Wallpaper collections: `壁纸合集/<collection>/<web group>/...`; single-group collections are flattened.
- Agent profiles: `代理档案/<agent>/意象影画/影画展示1.ext`, `影画展示2.ext`, `影画展示3.ext`; `代理档案/<agent>/角色展示/<tab_name>.ext`; `代理档案/<agent>/媒体物料/<tab_name>.ext`; `代理档案/<agent>/好感壁纸/<agent>好感壁纸.mp4`.
- Agent videos: `代理档案/<agent>/不可售影像.mp4` and `代理档案/<agent>/代理人档案.mp4`. Agent name is resolved from the video title and cross-matched against channel 43 canonical names.

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
- Agent cinema files are image tabs matching `影画展示\d` prefix from module 279. Most agents have three (`影画展示1/2/3`); special cases (e.g. 佩洛伊斯) may have fewer with suffixes like `影画展示1-哲`/`影画展示1-铃`. Preview/unreleased agents may have no cinema images; treat that as normal, not as a failure.
- Agent character display (角色展示) images/GIFs come from module 12 — collect all `map_desc` items unconditionally.
- Agent media materials (媒体物料) come from module 949 — collect all `map_desc` items unconditionally.
- Agent goodwill wallpapers (好感壁纸) come from channel 99 independent entry pages — extract MP4 via `data-video-url`.
- Calendar wallpaper modules expose group names such as `2026PC版壁纸收录` and `2026手机版壁纸收录`. Infer the year and PC/mobile suffix from those group names, and infer the month from tab names.
- Manifests and check reports are stored in `<dest>/.manifests/`. Only run `export-manifest` after the user explicitly asks to inspect or receive CSV files.
- Never delete user files automatically. If remote resources disappear, local files are extra, or old empty folders remain, report them and ask before deletion.
- Agent videos (`agent_videos`) come from channel 73 sub-items whose `entry_page` points to miyoushe articles. The workflow is: wiki entry → `ext.post_ext.post_id` → BBS post API → `vod_list[]` → pick highest-quality resolution. The BBS API (`bbs-api.miyoushe.com`) requires full browser security headers (`Sec-Fetch-*`, `Sec-Ch-Ua-*`, `Origin`) or it returns 403. Add `export https_proxy="socks5://127.0.0.1:2080"` before the Python command when the BBS API is IP-blocked.
- Wallpaper collection "六分街街头异闻" was formerly named "六分街街头热话"; the script uses the current name. Old local directories may need renaming.
