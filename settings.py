# -*- coding: utf-8 -*-
"""设置项：每个元素（字体/颜色/字号/加粗）以及水印、背景、方向等。

设置保存到 %APPDATA%\\月历纸生成器\\settings.json。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict, field


@dataclass
class ElementStyle:
    font: str = ""          # 字体显示名；"" 表示使用系统默认
    size: int = 16          # 字号（磅）
    color: str = "#000000"  # 颜色 #RRGGBB
    bold: bool = False
    mono: bool = True       # True=等距排版；False=非等距（按字体自然宽度）


@dataclass
class Settings:
    title: ElementStyle = field(default_factory=lambda: ElementStyle("", 36, "#000000", True))
    header_cn: ElementStyle = field(default_factory=lambda: ElementStyle("", 20, "#000000", True))
    header_en: ElementStyle = field(default_factory=lambda: ElementStyle("", 13, "#555555", False))
    week_number: ElementStyle = field(default_factory=lambda: ElementStyle("", 52, "#000000", True))
    week_number_top: ElementStyle = field(default_factory=lambda: ElementStyle("", 26, "#000000", True))
    week_number_bottom: ElementStyle = field(default_factory=lambda: ElementStyle("", 26, "#000000", True))
    day_number: ElementStyle = field(default_factory=lambda: ElementStyle("", 18, "#000000", False))
    lunar: ElementStyle = field(default_factory=lambda: ElementStyle("", 15, "#000000", False))
    festival: ElementStyle = field(default_factory=lambda: ElementStyle("", 14, "#C00000", False))
    watermark: ElementStyle = field(default_factory=lambda: ElementStyle("", 130, "#000000", True))

    watermark_enabled: bool = True
    watermark_alpha: int = 34          # 水印透明度 0~255
    bg_image: str = ""                 # 自定义背景图片路径（空 = 不使用）
    bg_alpha: int = 255                # 背景图整体透明度 0~255
    orientation: str = "landscape"     # landscape / portrait

    def element_list(self):
        return [
            ("title", "标题", self.title),
            ("header_cn", "表头中文", self.header_cn),
            ("header_en", "表头英文", self.header_en),
            ("week_number", "周次", self.week_number),
            ("week_number_top", "周次·左上", self.week_number_top),
            ("week_number_bottom", "周次·右下", self.week_number_bottom),
            ("day_number", "日期", self.day_number),
            ("lunar", "农历", self.lunar),
            ("festival", "节日/节气", self.festival),
            ("watermark", "水印", self.watermark),
        ]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        s = cls()
        for key, style in [("title", s.title), ("header_cn", s.header_cn),
                           ("header_en", s.header_en), ("week_number", s.week_number),
                           ("week_number_top", s.week_number_top),
                           ("week_number_bottom", s.week_number_bottom),
                           ("day_number", s.day_number), ("lunar", s.lunar),
                           ("festival", s.festival), ("watermark", s.watermark)]:
            if key in d and isinstance(d[key], dict):
                dd = d[key]
                style.font = str(dd.get("font", style.font))
                style.size = int(dd.get("size", style.size))
                style.color = str(dd.get("color", style.color))
                style.bold = bool(dd.get("bold", style.bold))
                style.mono = bool(dd.get("mono", style.mono))
        if "watermark_enabled" in d:
            s.watermark_enabled = bool(d["watermark_enabled"])
        if "watermark_alpha" in d:
            s.watermark_alpha = int(d["watermark_alpha"])
        if "bg_image" in d:
            s.bg_image = str(d["bg_image"])
        if "bg_alpha" in d:
            s.bg_alpha = int(d["bg_alpha"])
        if "orientation" in d:
            s.orientation = "landscape" if d["orientation"] != "portrait" else "portrait"
        return s


def _candidate_dirs() -> list:
    """设置文件的候选目录（优先 %APPDATA%，其次程序所在目录）。"""
    dirs = []
    base = os.environ.get("APPDATA")
    if base:
        dirs.append(os.path.join(base, "月历纸生成器"))
    try:
        if getattr(sys, "frozen", False):
            dirs.append(os.path.dirname(sys.executable))
        else:
            dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    try:
        dirs.append(os.getcwd())
    except Exception:
        pass
    return dirs


def settings_path():
    for d in _candidate_dirs():
        try:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "settings.json")
            # 探测可写性
            with open(p, "a", encoding="utf-8"):
                pass
            return p
        except Exception:
            continue
    return None


def load_settings() -> Settings:
    p = settings_path()
    try:
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return Settings.from_dict(json.load(f))
    except Exception:
        pass
    return Settings()


def save_settings(s: Settings) -> None:
    p = settings_path()
    if not p:
        return
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(s.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass
