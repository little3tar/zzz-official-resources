# ZZZ Official Resources Skill

用于拉取《绝区零》绳网情报站中公开整理的官方资源，并按本地目录结构保存、检查和补齐文件。项目本身不维护官方内容，也不拥有这些资源；它只是把已经整理好的公开资源清单转换为可下载、可校验、可修复的本地文件集合。

数据来源：[米游社·绝区零绳网情报站](https://baike.mihoyo.com/zzz/wiki/)

## 资源范围

当前清单共 `1904` 条资源：

| 类型 | 数量 | 说明 |
| --- | ---: | --- |
| `calendar` | 58 | 月历壁纸 |
| `wallpapers` | 1693 | 壁纸合集中的图片和动态壁纸视频 |
| `cinema` | 153 | 代理人意象影画 |

## 已下载资源

2026-05-05 已按当前目录结构完成一次本地补齐和检查，全部资源均已存在且非 0 字节。

共享快照：

- OneDrive：https://1drv.ms/f/c/0e07052ae732baff/IgDo0_7bteV-TK2GRifwPpTrAUM1jdhorYMhCNkgKsMa644?e=EgABsQ

共享文件是某次运行结果的快照。若需要确认远端是否有新增、移除或改名，仍建议重新运行 `check-remote` 或 `check-local`。

## 下载目录结构

执行 `download` 或 `repair` 时，脚本会把资源写入用户指定的 `--dest` 目录：

```text
<dest>/
  壁纸合集/
    月历壁纸合集/
      2024PC版壁纸收录/
        1月.jpeg
        ...
      2024手机版壁纸收录/
        1月.jpeg
        ...
      2025PC版壁纸收录/
      2025手机版壁纸收录/
      2026PC版壁纸收录/
      2026手机版壁纸收录/
    <collection>/
      <web group>/
        ...
  意象影画/
    <agent>/
      影画展示1.ext
      影画展示2.ext
      影画展示3.ext
```

月历壁纸使用绳网情报站页面中的官方分组名，例如 `2026PC版壁纸收录`、`2026手机版壁纸收录`；文件名使用页面中的月份标签，例如 `5月.png`。普通壁纸合集尽量保留页面中的合集和分组结构，少数单分组合集会扁平化到合集目录下。意象影画按代理人名称分目录保存。

## 命令

建议使用 Codex Desktop 捆绑的 Python：

```powershell
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\zzz_resources.py list-resources
```

常用命令：

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
- `download`、`repair`、`check-local` 和 `export-manifest` 需要指定 `--dest`。
- 受限网络、企业代理或沙箱环境中，远端检查和下载可能需要额外网络权限或代理配置。

## 状态文件

内部状态文件位于 `state/`：

- `state/calendar_manifest.csv`
- `state/wallpapers_manifest.csv`
- `state/cinema_manifest.csv`
- `state/last_check_report.csv`

这些文件记录当前资源清单和最近一次检查结果。默认不要把内部状态文件写入用户资源目录；只有明确需要导出清单时，才使用 `export-manifest`。

## 最近验证

验证日期：2026-05-05

已执行并通过：

- Python 语法编译检查。
- 重新读取月历页面，按官方分组生成月历目录。
- `check-local --type all` 对本地 OneDrive 目录检查，结果为 `records=1904 ok=1904`。
- 清理了旧月历命名逻辑留下的多余文件，并按官方分组重命名月历壁纸。

## 注意事项

- 不要自动删除用户目录中的文件；若发现远端移除、文件多余或空目录残留，应先报告。
- `check-remote` 会刷新内部清单并写入 `state/last_check_report.csv`。
- `check-local` 会根据远端当前数据刷新内部清单，并写入 `state/last_check_report.csv`。
- `repair` 只补下载缺失或 0 字节文件。
- 官方 Wiki 页面主体是前端壳，资源数据应通过脚本中的接口读取，不应直接解析可见 HTML。

## 致谢

感谢[米游社·绝区零绳网情报站](https://baike.mihoyo.com/zzz/wiki/)及诸多义务整理、补充和校对资源的【绳匠】。这个 skill 能够把资源拉取到本地，前提正是这些用户长期把官方资料整理成可浏览、可检索的 Wiki 内容。

这个 skill 的梳理、脚本实现、验证和 README 编写全程在 Codex 的帮助下完成。
