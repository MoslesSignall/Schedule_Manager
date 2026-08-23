# -*- coding: utf-8 -*-
"""字体枚举与等宽文本绘制。

- 自动读取电脑中所有字体（扫描 Windows 字体目录 + 注册表），
  返回“显示名 -> 字体文件”的映射；
- 提供等宽绘制：全角字符占 1 个字宽，半角字符占 0.5 个字宽，
  从而保证非等宽字体也能按等宽排布。
"""
from __future__ import annotations

import os
import unicodedata

from PIL import ImageFont, ImageDraw

_WIN_FONT_DIRS = [
    r"C:\Windows\Fonts",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"),
]

# 常见中文字体的英文族名 -> 中文显示名（用于下拉框更友好）
CN_ALIAS = {
    "simsun": "宋体",
    "nsimsun": "新宋体",
    "microsoft yahei": "微软雅黑",
    "microsoft yahei ui": "微软雅黑",
    "simhei": "黑体",
    "kaiti": "楷体",
    "fangsong": "仿宋",
    "lisu": "隶书",
    "simli": "隶书",
    "youyuan": "幼圆",
    "stkaiti": "华文楷体",
    "stxihei": "华文细黑",
    "stzhongsong": "华文中宋",
    "stfangsong": "华文仿宋",
    "stxinwei": "华文新魏",
    "stliti": "华文隶书",
    "stxingkai": "华文行楷",
    "dengxian": "等线",
    "kaiti sc": "楷体",
    "songti sc": "宋体",
    "heiti sc": "黑体",
}

# 字体族名(小写) -> 文件路径 的缓存
_family_to_file: dict | None = None
# 显示名 -> 文件路径
_display_to_file: dict | None = None
_display_list: list | None = None

_DEFAULT_CANDIDATES = [
    "Microsoft YaHei", "SimSun", "SimHei", "DengXian",
    "KaiTi", "FangSong", "Arial",
]


def is_fullwidth(ch: str) -> bool:
    """判断字符是否为全角（宽）字符。"""
    if ch in " \t":
        return False
    return unicodedata.east_asian_width(ch) in ("W", "F", "A")


def _iter_font_files():
    seen = set()
    for d in _WIN_FONT_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for n in names:
            if n.lower().endswith((".ttf", ".ttc", ".otf")):
                p = os.path.join(d, n)
                key = p.lower()
                if key not in seen:
                    seen.add(key)
                    yield p


def enumerate_fonts() -> list[str]:
    """枚举系统字体，返回排序后的“显示名”列表（同时填充缓存）。"""
    global _family_to_file, _display_to_file, _display_list
    if _display_list is not None:
        return _display_list

    family_to_file: dict = {}
    style_rank = {"regular": 0, "normal": 0, "book": 1, "medium": 2, "bold": 3}
    for p in _iter_font_files():
        try:
            f = ImageFont.truetype(p, 20)
            family, style = f.getname()
        except Exception:
            continue
        if not family:
            continue
        key = family.lower()
        rank = style_rank.get(style.lower(), 9)
        if key not in family_to_file:
            family_to_file[key] = (p, family, rank)
        else:
            if rank < family_to_file[key][2]:
                family_to_file[key] = (p, family, rank)

    _family_to_file = {k: v[0] for k, v in family_to_file.items()}

    display_to_file = {}
    display_list = []
    for key, (p, family, rank) in family_to_file.items():
        alias = CN_ALIAS.get(key, "")
        display = "%s (%s)" % (alias, family) if alias else family
        display_to_file[display] = p
        display_list.append(display)
    display_list.sort(key=lambda s: s.lower())
    _display_to_file = display_to_file
    _display_list = display_list
    return display_list


def resolve_file(display_name: str) -> str | None:
    """显示名 -> 字体文件路径；找不到返回 None。"""
    enumerate_fonts()
    p = _display_to_file.get(display_name)
    if p and os.path.exists(p):
        return p
    # 兼容：直接按族名查找
    low = display_name.lower()
    if low in _family_to_file:
        return _family_to_file[low]
    # 兜底：找默认字体
    for cand in _DEFAULT_CANDIDATES:
        if cand.lower() in _family_to_file:
            return _family_to_file[cand.lower()]
    return None


def _default_font_path() -> str | None:
    enumerate_fonts()
    for cand in _DEFAULT_CANDIDATES:
        if cand.lower() in _family_to_file:
            return _family_to_file[cand.lower()]
    # 任意一个可用字体
    for p in (_family_to_file or {}).values():
        return p
    return None


def load_font(display_name: str, size_px: int) -> ImageFont.FreeTypeFont:
    """加载字体（显示名 -> 字体）。失败时退回默认字体。"""
    size_px = max(1, int(size_px))
    path = resolve_file(display_name)
    try:
        if path:
            return ImageFont.truetype(path, size_px)
    except Exception:
        pass
    dp = _default_font_path()
    try:
        if dp:
            return ImageFont.truetype(dp, size_px)
    except Exception:
        pass
    return ImageFont.load_default()


def text_width(text: str, size_px: int, mono: bool = True, font=None) -> float:
    """计算文本宽度。

    mono=True：等宽规则（全角=1em，半角=0.5em）。
    mono=False：按字体自然宽度（需传入 font）。
    """
    if not mono and font is not None:
        try:
            return font.getlength(text)
        except Exception:
            pass
    total = 0.0
    for ch in text:
        total += size_px if is_fullwidth(ch) else size_px * 0.5
    return total


def draw_text(draw: ImageDraw.ImageDraw, text: str, x: float, y: float,
              font: ImageFont.FreeTypeFont, fill, anchor: str = "l",
              bold: bool = False, mono: bool = True) -> float:
    """绘制文本。

    anchor 水平取值：'l' 左对齐、'c' 居中、'r' 右对齐（x 为参考点）。
    y 为文本顶部。返回文本总宽度。

    mono=True ：等宽排版（全角 1em、半角 0.5em，逐字符居中到单元格），
               保证非等宽字体也能对齐。
    mono=False：非等距，按字体自然宽度整体绘制。
    """
    if not text:
        return 0.0
    size = font.size
    stroke = max(1, int(size / 16)) if bold else 0

    if not mono:
        anchor_map = {"l": "la", "c": "ma", "r": "ra"}
        draw.text((x, y), text, font=font, fill=fill,
                  anchor=anchor_map.get(anchor, "la"),
                  stroke_width=stroke, stroke_fill=fill)
        try:
            return font.getlength(text)
        except Exception:
            return size * 0.5 * len(text)

    total = text_width(text, size, mono=True)
    if anchor == "c":
        cur = x - total / 2.0
    elif anchor == "r":
        cur = x - total
    else:
        cur = x

    for ch in text:
        cw = size if is_fullwidth(ch) else size * 0.5
        try:
            gw = font.getlength(ch)
        except Exception:
            gw = cw
        gx = cur + (cw - gw) / 2.0
        draw.text((gx, y), ch, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=fill)
        cur += cw
    return total
