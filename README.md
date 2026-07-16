# ZZZ Official Resources Skill

用于拉取《绝区零》绳网情报站中公开整理的官方资源，并按本地目录结构保存、检查和补齐文件。项目本身不维护官方内容，也不拥有这些资源；它只是把已经整理好的公开资源清单转换为可下载、可校验、可修复的本地文件集合。

数据来源：[米游社·绝区零绳网情报站](https://baike.mihoyo.com/zzz/wiki/)

## 资源范围

当前清单共 `3033` 条资源：

| 类型 | 数量 | 说明 |
| --- | ---: | --- |
| `wallpapers` | 2223 | 壁纸合集（含月历、EP短片、阵营、节日、活动、New Eridan 时尚等） |
| `cinema` | 698 | 代理档案（意象影画、角色展示、媒体物料） |
| `goodwill` | 57 | 好感壁纸视频 |
| `agent_videos` | 55 | 代理人视频（不可售影像 42、代理人档案 13） |

## OneDrive 共享

本地整理好的完整资源已在 OneDrive 共享：

https://1drv.ms/f/c/0e07052ae732baff/IgDo0_7bteV-TK2GRifwPpTrAUM1jdhorYMhCNkgKsMa644?e=pucHMa

共享文件是某次运行结果的快照。若需确认远端是否有新增、移除或改名，建议重新运行 `check-remote` 或 `check-local`。

## 下载目录结构

```text
<dest>/
  壁纸合集/
    月历壁纸合集/
      2024PC版壁纸收录/ ...
      2024手机版壁纸收录/ ...
      ...
    EP短片壁纸合集/ ...
    动态壁纸合集/ ...
    影像档案壁纸合集/ ...
    阵营壁纸合集/ ...
    节日壁纸合集/ ...
    活动壁纸合集/ ...
    生日贺图壁纸合集/ ...
    过塑手账壁纸合集/ ...
    丽都放大镜壁纸合集/ ...
    New Eridan 时尚/ ...
    丽都有丽事/ ...
    六分街街头异闻/ ...
    邦布们的说明书/ ...
  代理档案/
    <agent>/
      意象影画/
        影画展示1.ext
        影画展示2.ext
        影画展示3.ext
      角色展示/
        <tab_name>.gif / .png
      媒体物料/
        <tab_name>.png / .gif
      好感壁纸/
        <agent>好感壁纸.mp4
      不可售影像.mp4
      代理人档案.mp4
```

月历壁纸使用官方分组名（如 `2026PC版壁纸收录`）；文件名使用页面标签。普通壁纸合集保留页面分组结构，`丽都有丽事` 和 `邦布们的说明书` 按 tab 命名自动识别系列子文件夹。代理档案统一归入 `代理档案/<agent>/`，其下包含意象影画、角色展示、媒体物料、好感壁纸四个子目录及不可售影像、代理人档案两个视频文件。

## 命令

```powershell
python scripts/zzz_resources.py list-resources --dest "C:\path\to\resources"
python scripts/zzz_resources.py check-remote --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py check-local --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py download --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py repair --type all --dest "C:\path\to\resources"
python scripts/zzz_resources.py export-manifest --type all --manifest-src "C:\path\to\resources" --dest "C:\path\for\csv"
```

`--type` 支持：`wallpapers`、`cinema`、`goodwill`、`agent_videos`、`all`

## 运行环境

- Python 3，仅标准库，无第三方依赖。
- `check-remote`、`check-local`、`download`、`repair` 会访问米游社 Wiki 接口。
- 所有命令都需指定 `--dest`（项目根目录）。

## 清单文件

清单和报告存储在 `<dest>/.manifests/`：

- `wallpapers_manifest.csv`
- `cinema_manifest.csv`
- `goodwill_manifest.csv`
- `agent_videos_manifest.csv`
- `last_check_report.csv`

这些文件随项目走，`check-remote` 和 `download`/`repair` 会自动刷新。

## 注意事项

- 不自动删除用户文件；远端移除或本地多余文件应先报告。
- 官方 Wiki 页面是前端壳，资源数据应通过 `entry_page` API 读取，不解析可见 HTML。
- `repair` 只补下载缺失或 0 字节文件。
- `agent_videos` 需通过米游社 BBS API 获取视频链接，该 API 要求完整浏览器安全头（`Sec-Fetch-*` 等）；若被限流，设置 `export https_proxy="socks5://127.0.0.1:2080"` 后再运行命令。

## 致谢

感谢[米游社·绝区零绳网情报站](https://baike.mihoyo.com/zzz/wiki/)及诸多义务整理、补充和校对资源的【绳匠】。

这个 skill 的梳理、脚本实现、验证和文档编写全程在 Claude Code、Codex 和 DeepSeek 的帮助下完成。
