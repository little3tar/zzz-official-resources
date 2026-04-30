# ZZZ Official Resources Skill

这是一个用于拉取《绝区零》官方资源的 Codex skill。它通过米游社·绝区零绳网情报站公开整理的 Wiki 数据接口读取资源清单，并把图片、视频等资源下载到本地指定目录。

这个项目不负责维护官方内容本身，也不声称拥有这些资源；它只是把已经整理好的公开资源结构化为本地可检查、可下载、可修复的文件集合。

## 能力范围

- 日历壁纸：拉取官方月历壁纸资源。
- 壁纸合集：拉取壁纸合集页面中的静态图片和动态壁纸视频。
- 代理人意象影画：拉取代理人影画展示图。

当前内置清单规模：

- `calendar`：56 条
- `wallpapers`：1691 条
- `cinema`：153 条
- 合计：1900 条

## 已下载资源共享

2026-04-29 运行本 skill 拉取到的完整资源，已分别上传到 Google Drive 和 OneDrive，并开启共享。需要直接获取已下载资源时，可以使用下面的链接：

- Google Drive：https://drive.google.com/drive/folders/1dhHrK1h-rSo_LSU9s5YW5IIJf0dC23Zd?usp=sharing
- OneDrive：https://1drv.ms/f/c/0e07052ae732baff/IgDo0_7bteV-TK2GRifwPpTrAUM1jdhorYMhCNkgKsMa644?e=EgABsQ

这些共享文件是某次运行结果的快照。若需要确认是否有新增、移除或改名的远端资源，仍建议使用 `check-remote` 重新检查。

## 下载目录结构

执行 `download` 或 `repair` 时，脚本会把资源写入用户指定的 `--dest` 目录，并按当前共享目录结构组织文件：

```text
<dest>/
  壁纸合集/
    月历壁纸合集/
      <year>/
        YYYYMMp.ext
        YYYYMMm.ext
    <collection>/
      <web group>/
        ...
  意象影画/
    <agent>/
      影画展示1.ext
      影画展示2.ext
      影画展示3.ext
```

日历壁纸已归入 `壁纸合集/月历壁纸合集/`。其中 `p` 表示 PC 版，`m` 表示移动端版。壁纸合集会尽量保留绳网情报站页面中的合集和分组结构；少数单分组合集会被扁平化到合集目录下。代理人意象影画按代理人名称分目录保存到 `意象影画/`。

## 命令

建议使用 Codex Desktop 捆绑的 Python 运行：

```powershell
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\zzz_resources.py list-resources
```

也可以在系统 Python 可用时使用：

```powershell
python scripts\zzz_resources.py list-resources
```

可用命令：

```powershell
python scripts\zzz_resources.py list-resources
python scripts\zzz_resources.py check-remote --type all
python scripts\zzz_resources.py check-local --type all --dest "C:\path\to\resources"
python scripts\zzz_resources.py download --type all --dest "C:\path\to\resources"
python scripts\zzz_resources.py repair --type all --dest "C:\path\to\resources"
python scripts\zzz_resources.py export-manifest --type all --dest "C:\path\to\csv"
```

`--type` 支持：

- `calendar`
- `wallpapers`
- `cinema`
- `all`

## 运行环境

- Python 3。
- 仅使用 Python 标准库，不需要额外安装第三方依赖。
- `check-remote`、`check-local`、`download`、`repair` 会访问米游社 Wiki 相关接口。
- `download`、`repair`、`check-local` 和 `export-manifest` 需要用户指定 `--dest`。
- 在受限沙箱、企业网络或代理环境中，远端检查和下载可能需要额外网络权限或代理配置。

## 状态文件

内部状态文件位于 `state/`：

- `state/calendar_manifest.csv`
- `state/wallpapers_manifest.csv`
- `state/cinema_manifest.csv`
- `state/last_check_report.csv`

这些文件用于记录当前资源清单和最近一次检查结果。默认不要把内部状态文件写入用户资源目录；只有用户明确需要导出清单时，才使用 `export-manifest`。

## 本次验证

验证日期：2026-04-29

已执行并通过：

- Python 语法编译检查。
- `--help` 命令检查。
- `list-resources` 清单读取检查。
- `check-remote --type all` 远端接口检查，结果为 `records=1900 unchanged=1900`。
- `check-local --type all` 对空临时目录检查，结果为 `records=1900 missing=1900`。
- `export-manifest --type all` 对临时目录导出检查，结果为 `exported=4`。

未执行完整下载和修复测试，因为这会批量下载大量图片和视频资源到用户目录。当前命令结构和远端数据读取已验证可用。

## 注意事项

- 不要自动删除用户目录中的文件；若发现远端移除、文件多余或空目录残留，应先报告。
- `check-remote` 会刷新内部清单并写入 `state/last_check_report.csv`。
- `check-local` 会根据远端当前数据刷新内部清单，并写入 `state/last_check_report.csv`。
- `repair` 只补下载缺失或 0 字节文件。
- 官方 Wiki 页面主体是前端壳，资源数据应通过脚本中的接口读取，不应直接解析可见 HTML。

## 致谢

感谢[米游社·绝区零绳网情报站](https://baike.mihoyo.com/zzz/wiki/)及诸多义务整理、补充和校对资源的【绳匠】。这个 skill 能够把资源拉取到本地，前提正是这些用户长期把官方资料整理成可浏览、可检索的 Wiki 内容。

这个 skill 的梳理、脚本实现、验证和 README 编写全程在 Codex 的帮助下完成。
