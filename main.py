# -*- coding: utf-8 -*-
"""月历纸生成器 —— 程序入口。"""
from __future__ import annotations

import os
import sys


def _bootstrap():
    # 开发时从 vendor 目录加载依赖；打包后由 PyInstaller 内置，无需此目录
    base = os.path.dirname(os.path.abspath(__file__))
    vendor = os.path.join(base, "vendor")
    if os.path.isdir(vendor) and vendor not in sys.path:
        sys.path.insert(0, vendor)


def main():
    _bootstrap()
    from gui import App
    App().run()


if __name__ == "__main__":
    main()
