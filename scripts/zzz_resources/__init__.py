"""绝区零官方资源下载与校验工具。"""

from .cli import main
from .records import compare_remote_records

__all__ = ["compare_remote_records", "main"]
