# -*- coding: utf-8 -*-
"""渲染器：把某个月的日历绘制为 A4 尺寸的 PIL 图像。

支持：7 行 × 8 列表格、逐元素字体/颜色/字号、等宽排版、
月英文简写水印（可开关/透明度）、自定义背景图（透明度）。
导出用 300 DPI，预览可用较低 DPI 提速。
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

import core
import fonts
from settings import Settings

# 参考图比例：表格高度/宽度 ≈ 0.693，各行高度占比
RATIO_HW = 501.0 / 723.0
FRAC_TITLE = 36.8 / 501.0
FRAC_HEADER = 68.2 / 501.0

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
WEEKDAY_EN = ["M O N", "T U E", "W E D", "T H U", "F R I", "S A T", "S U N"]


def _hex_to_rgb(hx: str):
    hx = (hx or "#000000").lstrip("#")
    try:
        return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
    except Exception:
        return (0, 0, 0)


def _pt(pt: int | float, dpi: int) -> int:
    return max(1, round(float(pt) * dpi / 72.0))


def _load(style, size_pt, dpi):
    return fonts.load_font(style.font, _pt(size_pt, dpi))


def page_size(orientation: str, dpi: int = 300):
    mm = dpi / 25.4
    if orientation == "portrait":
        return (round(210 * mm), round(297 * mm))
    return (round(297 * mm), round(210 * mm))


def _layout(orientation: str, dpi: int = 300):
    """返回 (pw, ph, tx, ty, tw, th, cw, rows_y)。"""
    mm = dpi / 25.4
    pw, ph = page_size(orientation, dpi)
    if orientation == "portrait":
        ml = mr = 12 * mm
        tw = pw - ml - mr
        th = tw * RATIO_HW
        tx, ty = ml, (ph - th) / 2.0
    else:
        ml = mr = 12 * mm
        mt = mb = 9 * mm
        tx, ty = ml, mt
        tw = pw - ml - mr
        th = ph - mt - mb

    title_h = th * FRAC_TITLE
    header_h = th * FRAC_HEADER
    data_h = (th - title_h - header_h) / 5.0

    cw = tw / 8.0
    rows_y = []
    y = ty
    rows_y.append((y, y + title_h))
    y += title_h
    rows_y.append((y, y + header_h))
    y += header_h
    for _ in range(5):
        rows_y.append((y, y + data_h))
        y += data_h
    return pw, ph, tx, ty, tw, th, cw, rows_y


def _scale_cover(img: Image.Image, size):
    iw, ih = img.size
    tw, th = size
    scale = max(tw / iw, th / ih)
    nw, nh = round(iw * scale), round(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def render_calendar(year: int, month: int, s: Settings, dpi: int = 300) -> Image.Image:
    pw, ph, tx, ty, tw, th, cw, rows_y = _layout(s.orientation, dpi)

    # 1) 背景（白色 或 自定义图片 + 透明度）
    if s.bg_image and os.path.exists(s.bg_image):
        try:
            bg = Image.open(s.bg_image).convert("RGBA")
            bg = _scale_cover(bg, (pw, ph))
            if s.bg_alpha < 255:
                r, g, b, a = bg.split()
                a = a.point(lambda x: x * max(0, min(255, s.bg_alpha)) // 255)
                bg = Image.merge("RGBA", (r, g, b, a))
            img = Image.new("RGBA", (pw, ph), (255, 255, 255, 255))
            img.alpha_composite(bg)
        except Exception:
            img = Image.new("RGBA", (pw, ph), (255, 255, 255, 255))
    else:
        img = Image.new("RGBA", (pw, ph), (255, 255, 255, 255))

    # 2) 水印（月份英文简写）
    if s.watermark_enabled:
        abbr = core.MONTH_ABBR[month - 1]
        wm_rgb = _hex_to_rgb(s.watermark.color)
        overlay = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        wfont = _load(s.watermark, s.watermark.size, dpi)
        cx, cy = pw / 2.0, ph / 2.0
        asc, desc = wfont.getmetrics()
        y = cy - (asc + desc) / 2.0
        alpha = max(0, min(255, int(s.watermark_alpha)))
        fonts.draw_text(od, core.MONTH_ABBR[month - 1], cx, y, wfont,
                        fill=(wm_rgb[0], wm_rgb[1], wm_rgb[2], alpha),
                        anchor="c", bold=s.watermark.bold, mono=s.watermark.mono)
        img.alpha_composite(overlay)

    draw = ImageDraw.Draw(img)

    # 3) 表格网格线（1pt 宽）
    line_w = max(2, round(dpi / 72.0))
    line_color = (0, 0, 0)
    for i in range(9):
        x = tx + i * cw
        if i == 0 or i == 8:
            draw.line([(x, ty), (x, ty + th)], fill=line_color, width=line_w)
        else:
            draw.line([(x, rows_y[1][0]), (x, ty + th)], fill=line_color, width=line_w)
    for (ytop, _) in rows_y:
        draw.line([(tx, ytop), (tx + tw, ytop)], fill=line_color, width=line_w)
    draw.line([(tx, ty + th), (tx + tw, ty + th)], fill=line_color, width=line_w)

    # 4) 标题（第 1 行，整行合并）
    tfont = _load(s.title, s.title.size, dpi)
    ttext = "%d年%d月" % (year, month)
    tcolor = _hex_to_rgb(s.title.color)
    ty1, ty2 = rows_y[0]
    asc, desc = tfont.getmetrics()
    fonts.draw_text(draw, ttext, tx + tw / 2.0, ty1 + (ty2 - ty1 - (asc + desc)) / 2.0,
                    tfont, tcolor, anchor="c", bold=s.title.bold, mono=s.title.mono)

    # 5) 表头（第 2 行）
    h_cn_font = _load(s.header_cn, s.header_cn.size, dpi)
    h_en_font = _load(s.header_en, s.header_en.size, dpi)
    hy1, hy2 = rows_y[1]
    cn_asc, cn_desc = h_cn_font.getmetrics()
    en_asc, en_desc = h_en_font.getmetrics()
    cn_h, en_h = cn_asc + cn_desc, en_asc + en_desc
    gap = (hy2 - hy1) * 0.08
    total = cn_h + gap + en_h
    y_cn = hy1 + (hy2 - hy1 - total) / 2.0
    y_en = y_cn + cn_h + gap
    cn_color = _hex_to_rgb(s.header_cn.color)
    en_color = _hex_to_rgb(s.header_en.color)

    for i in range(8):
        cx = tx + cw * i + cw / 2.0
        if i == 0:
            cn_txt, en_txt = "周次", "W E E K"
        else:
            cn_txt, en_txt = WEEKDAY_CN[i - 1], WEEKDAY_EN[i - 1]
        fonts.draw_text(draw, cn_txt, cx, y_cn, h_cn_font, cn_color,
                        anchor="c", bold=s.header_cn.bold, mono=s.header_cn.mono)
        fonts.draw_text(draw, en_txt, cx, y_en, h_en_font, en_color,
                        anchor="c", bold=s.header_en.bold, mono=s.header_en.mono)

    # 6) 数据行（第 3~7 行）
    rows = core.build_month(year, month)
    pad_x = cw * 0.07
    pad_y = (rows_y[2][1] - rows_y[2][0]) * 0.06
    day_font = _load(s.day_number, s.day_number.size, dpi)
    lunar_font = _load(s.lunar, s.lunar.size, dpi)
    fest_font = _load(s.festival, s.festival.size, dpi)
    week_font = _load(s.week_number, s.week_number.size, dpi)
    week_top_font = _load(s.week_number_top, s.week_number_top.size, dpi)
    week_bottom_font = _load(s.week_number_bottom, s.week_number_bottom.size, dpi)
    day_color = _hex_to_rgb(s.day_number.color)
    lunar_color = _hex_to_rgb(s.lunar.color)
    fest_color = _hex_to_rgb(s.festival.color)
    week_color = _hex_to_rgb(s.week_number.color)
    week_top_color = _hex_to_rgb(s.week_number_top.color)
    week_bottom_color = _hex_to_rgb(s.week_number_bottom.color)

    for ridx in range(5):
        if ridx >= len(rows):
            break
        row = rows[ridx]
        rytop, rybot = rows_y[2 + ridx]
        cell_h = rybot - rytop

        if row.week_label2:
            # 一行合并两周：右上到左下的斜线，左上/右下两个三角形各写一个周次
            draw.line([(tx + cw, rytop), (tx, rybot)], fill=line_color, width=line_w)
            if row.week_label:
                a, d_ = week_top_font.getmetrics()
                cx1 = tx + cw / 3.0
                cy1 = rytop + cell_h / 3.0
                fonts.draw_text(draw, row.week_label, cx1, cy1 - (a + d_) / 2.0,
                                week_top_font, week_top_color, anchor="c",
                                bold=s.week_number_top.bold, mono=s.week_number_top.mono)
            if row.week_label2:
                a, d_ = week_bottom_font.getmetrics()
                cx2 = tx + cw * 2.0 / 3.0
                cy2 = rytop + cell_h * 2.0 / 3.0
                fonts.draw_text(draw, row.week_label2, cx2, cy2 - (a + d_) / 2.0,
                                week_bottom_font, week_bottom_color, anchor="c",
                                bold=s.week_number_bottom.bold, mono=s.week_number_bottom.mono)
        elif row.week_label:
            w_asc, w_desc = week_font.getmetrics()
            wcx = tx + cw / 2.0
            wy = rytop + (rybot - rytop - (w_asc + w_desc)) / 2.0
            fonts.draw_text(draw, row.week_label, wcx, wy, week_font, week_color,
                            anchor="c", bold=s.week_number.bold, mono=s.week_number.mono)

        for i in range(7):
            day = row.days[i]
            if day is None:
                continue
            cell_left = tx + cw * (i + 1)
            cell_top = rytop + pad_y
            x = cell_left + pad_x
            dnum = str(day.day)
            fonts.draw_text(draw, dnum, x, cell_top, day_font, day_color,
                            anchor="l", bold=s.day_number.bold, mono=s.day_number.mono)
            x += fonts.text_width(dnum, day_font.size, mono=s.day_number.mono,
                                  font=day_font) + day_font.size * 0.5
            if day.secondary_kind == "festival":
                fonts.draw_text(draw, day.secondary_text, x, cell_top, fest_font,
                                fest_color, anchor="l", bold=s.festival.bold, mono=s.festival.mono)
            else:
                fonts.draw_text(draw, day.secondary_text, x, cell_top, lunar_font,
                                lunar_color, anchor="l", bold=s.lunar.bold, mono=s.lunar.mono)

    return img.convert("RGB")
