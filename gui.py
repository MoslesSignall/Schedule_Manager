# -*- coding: utf-8 -*-
"""月历纸生成器 —— 图形界面（customtkinter）。"""
from __future__ import annotations

import calendar
import os
import threading
from datetime import date, timedelta
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk
from PIL import Image

import core
import fonts
import renderer
from settings import Settings, load_settings, save_settings, ElementStyle

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ELEMENT_RANGES = {
    "title": (1, 80),
    "header_cn": (1, 44),
    "header_en": (1, 32),
    "week_number": (1, 96),
    "week_number_top": (1, 80),
    "week_number_bottom": (1, 80),
    "day_number": (1, 44),
    "lunar": (1, 32),
    "festival": (1, 32),
    "watermark": (1, 360),
}


def default_year_month():
    """默认年月：当前月；若处于本月最后一周则跳到下月。"""
    today = date.today()
    y, m, d = today.year, today.month, today.day
    dim = calendar.monthrange(y, m)[1]
    last_day = date(y, m, dim)
    last_week_monday = last_day - timedelta(days=last_day.weekday())
    if today >= last_week_monday:
        m += 1
        if m > 12:
            m = 1
            y += 1
        if y > 2099:
            y, m = 2099, 12
    return y, m


def _best_default_font(names):
    for key in ("微软雅黑", "Microsoft YaHei", "宋体", "SimSun", "黑体", "SimHei"):
        for n in names:
            if key.lower() in n.lower():
                return n
    return names[0] if names else ""


class StyleCard:
    """一个元素的样式编辑卡片。"""

    def __init__(self, parent, key: str, label: str, style: ElementStyle,
                 size_range, on_change, get_fonts):
        self.key = key
        self.label = label
        self.style = style
        self.on_change = on_change
        self.get_fonts = get_fonts
        self.frame = ctk.CTkFrame(parent, corner_radius=8)
        self.frame.pack(fill="x", padx=8, pady=5)

        head = ctk.CTkFrame(self.frame, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(head, text=label, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(side="left")

        # 字体
        self.font_combo = ctk.CTkComboBox(self.frame, values=["加载中…"],
                                          command=lambda _e: self._changed_font())
        self.font_combo.pack(fill="x", padx=8, pady=(0, 4))

        row = ctk.CTkFrame(self.frame, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(0, 2))
        ctk.CTkLabel(row, text="字号").pack(side="left")
        self.size_slider = ctk.CTkSlider(row, from_=size_range[0], to=size_range[1],
                                         number_of_steps=size_range[1] - size_range[0],
                                         width=110, command=lambda _v: self._changed_size())
        self.size_slider.pack(side="left", padx=6)
        self.size_label = ctk.CTkLabel(row, text=str(style.size), width=30)
        self.size_label.pack(side="left")

        ctk.CTkLabel(row, text="颜色").pack(side="left", padx=(8, 0))
        self.color_btn = ctk.CTkButton(row, text="", width=34, height=22,
                                       corner_radius=6, command=self._pick_color)
        self.color_btn.pack(side="left", padx=4)

        row2 = ctk.CTkFrame(self.frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(0, 8))
        self.bold_chk = ctk.CTkCheckBox(row2, text="粗体", command=self._changed_bold,
                                        width=20)
        self.bold_chk.pack(side="left", padx=(0, 12))
        self.mono_chk = ctk.CTkCheckBox(row2, text="等距", command=self._changed_mono,
                                        width=20)
        self.mono_chk.pack(side="left")

        self._sync()

    def _changed_font(self):
        self.style.font = self.font_combo.get()
        self.on_change()

    def _changed_size(self):
        self.style.size = int(round(self.size_slider.get()))
        self.size_label.configure(text=str(self.style.size))
        self.on_change()

    def _changed_bold(self):
        self.style.bold = bool(self.bold_chk.get())
        self.on_change()

    def _changed_mono(self):
        self.style.mono = bool(self.mono_chk.get())
        self.on_change()

    def _pick_color(self):
        rgb, hx = colorchooser.askcolor(color=self.style.color, title="选择颜色 - " + self.label)
        if hx:
            self.style.color = hx
            self._sync_color()
            self.on_change()

    def _sync_color(self):
        try:
            self.color_btn.configure(fg_color=self.style.color, hover_color=self.style.color)
        except Exception:
            pass

    def _sync(self):
        names = self.get_fonts()
        if names:
            if self.font_combo.cget("values") != tuple(names):
                self.font_combo.configure(values=names)
        cur = self.style.font
        if cur and cur in names:
            self.font_combo.set(cur)
        elif names:
            self.font_combo.set(_best_default_font(names))
            self.style.font = _best_default_font(names)
        self.size_slider.set(self.style.size)
        self.size_label.configure(text=str(self.style.size))
        self.bold_chk.select() if self.style.bold else self.bold_chk.deselect()
        self.mono_chk.select() if self.style.mono else self.mono_chk.deselect()
        self._sync_color()

    def refresh_fonts(self):
        self._sync()


class App:
    def __init__(self):
        self.settings = load_settings()
        self.year, self.month = default_year_month()
        self.font_names: list = []
        self._preview_job = None
        self._save_job = None
        self._resize_job = None
        self._preview_img_ref = None
        self._preview_img = None
        self._zoom = 1.0

        self.win = ctk.CTk()
        self.win.title("月历纸生成器")
        self.win.geometry("1320x880")
        self.win.minsize(1100, 700)

        self._build()

        # 后台加载字体
        threading.Thread(target=self._load_fonts, daemon=True).start()

        self._schedule_preview()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------
    def _build(self):
        self.left = ctk.CTkScrollableFrame(self.win, width=430)
        self.left.pack(side="left", fill="y", padx=(8, 4), pady=8)

        self.right = ctk.CTkFrame(self.win, corner_radius=8)
        self.right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        # 预览工具栏
        bar = ctk.CTkFrame(self.right, fg_color="transparent")
        bar.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkButton(bar, text="适应窗口", width=78, command=self._preview_fit).pack(side="left", padx=2)
        ctk.CTkButton(bar, text="−", width=34, command=self._preview_zoom_out).pack(side="left", padx=2)
        ctk.CTkButton(bar, text="＋", width=34, command=self._preview_zoom_in).pack(side="left", padx=2)
        self.zoom_label = ctk.CTkLabel(bar, text="适应", width=70)
        self.zoom_label.pack(side="left", padx=8)

        # 可滚动预览
        self.preview_scroll = ctk.CTkScrollableFrame(self.right, corner_radius=0,
                                                     fg_color="transparent")
        self.preview_scroll.pack(fill="both", expand=True, padx=8, pady=8)
        self.preview_label = ctk.CTkLabel(self.preview_scroll, text="正在生成预览…")
        self.preview_label.pack(padx=6, pady=6)
        self.right.bind("<Configure>", self._on_preview_resize)

        # 年月
        ym = ctk.CTkFrame(self.left, corner_radius=8)
        ym.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(ym, text="导出月份", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        r = ctk.CTkFrame(ym, fg_color="transparent")
        r.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(r, text="年").pack(side="left")
        self.year_combo = ctk.CTkComboBox(r, values=[str(y) for y in range(2000, 2100)],
                                          width=90, command=lambda _e: self._on_ym())
        self.year_combo.pack(side="left", padx=4)
        self.year_combo.set(str(self.year))
        ctk.CTkLabel(r, text="月").pack(side="left", padx=(8, 0))
        self.month_combo = ctk.CTkComboBox(r, values=[str(m) for m in range(1, 13)],
                                           width=70, command=lambda _e: self._on_ym())
        self.month_combo.pack(side="left", padx=4)
        self.month_combo.set(str(self.month))
        ctk.CTkButton(r, text="当前月", width=66, command=self._go_current).pack(side="left", padx=(8, 0))

        # 导出
        ex = ctk.CTkFrame(self.left, corner_radius=8)
        ex.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(ex, text="导出", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        er = ctk.CTkFrame(ex, fg_color="transparent")
        er.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkButton(er, text="导出 PDF", height=34, command=self._export_pdf).pack(side="left", expand=True, fill="x", padx=3)
        ctk.CTkButton(er, text="导出 PNG", height=34, fg_color="#3a7d44", hover_color="#2f6537",
                      command=lambda: self._export_image("png")).pack(side="left", expand=True, fill="x", padx=3)
        ctk.CTkButton(er, text="导出 JPG", height=34, fg_color="#8a6d1a", hover_color="#6f5715",
                      command=lambda: self._export_image("jpg")).pack(side="left", expand=True, fill="x", padx=3)

        # 方向
        ori = ctk.CTkFrame(self.left, corner_radius=8)
        ori.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(ori, text="纸张方向（A4）", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.ori_seg = ctk.CTkSegmentedButton(ori, values=["横向", "纵向"],
                                              command=self._on_orientation)
        self.ori_seg.pack(fill="x", padx=10, pady=(2, 10))
        self.ori_seg.set("横向" if self.settings.orientation == "landscape" else "纵向")

        # 样式卡片
        ctk.CTkLabel(self.left, text="元素样式", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(8, 0))
        self.cards: dict[str, StyleCard] = {}
        for key, label, style in self.settings.element_list():
            self.cards[key] = StyleCard(self.left, key, label, style, ELEMENT_RANGES[key],
                                        self._on_style_change, self._get_fonts)

        # 水印
        wm = ctk.CTkFrame(self.left, corner_radius=8)
        wm.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(wm, text="背景水印", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.wm_chk = ctk.CTkCheckBox(wm, text="显示月份英文简写水印（如 JUL / SEP）",
                                      command=self._on_style_change)
        self.wm_chk.pack(anchor="w", padx=10, pady=4)
        wr = ctk.CTkFrame(wm, fg_color="transparent")
        wr.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(wr, text="透明度").pack(side="left")
        self.wm_alpha = ctk.CTkSlider(wr, from_=0, to=255, number_of_steps=255, width=140,
                                      command=lambda _v: self._on_style_change())
        self.wm_alpha.pack(side="left", padx=6)
        self.wm_alpha_label = ctk.CTkLabel(wr, text=str(self.settings.watermark_alpha), width=34)
        self.wm_alpha_label.pack(side="left")
        self._sync_wm()

        # 背景图
        bg = ctk.CTkFrame(self.left, corner_radius=8)
        bg.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(bg, text="自定义背景图片", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))
        br = ctk.CTkFrame(bg, fg_color="transparent")
        br.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(br, text="选择图片", width=90, command=self._choose_bg).pack(side="left", padx=2)
        ctk.CTkButton(br, text="清除", width=60, fg_color="#a33", hover_color="#822",
                      command=self._clear_bg).pack(side="left", padx=2)
        self.bg_label = ctk.CTkLabel(br, text="未选择", anchor="w")
        self.bg_label.pack(side="left", padx=6, fill="x", expand=True)
        bgr = ctk.CTkFrame(bg, fg_color="transparent")
        bgr.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(bgr, text="透明度").pack(side="left")
        self.bg_alpha = ctk.CTkSlider(bgr, from_=0, to=255, number_of_steps=255, width=140,
                                      command=lambda _v: self._on_style_change())
        self.bg_alpha.pack(side="left", padx=6)
        self.bg_alpha_label = ctk.CTkLabel(bgr, text=str(self.settings.bg_alpha), width=34)
        self.bg_alpha_label.pack(side="left")
        self._sync_bg()

        # 重置
        ctk.CTkButton(self.left, text="恢复默认设置", fg_color="#666", hover_color="#555",
                      command=self._reset_defaults).pack(fill="x", padx=8, pady=(8, 12))

    # ---------------- 状态同步 ----------------
    def _get_fonts(self):
        return self.font_names

    def _sync_wm(self):
        self.wm_chk.select() if self.settings.watermark_enabled else self.wm_chk.deselect()
        self.wm_alpha.set(self.settings.watermark_alpha)
        self.wm_alpha_label.configure(text=str(self.settings.watermark_alpha))

    def _sync_bg(self):
        if self.settings.bg_image:
            self.bg_label.configure(text=os.path.basename(self.settings.bg_image))
        else:
            self.bg_label.configure(text="未选择")
        self.bg_alpha.set(self.settings.bg_alpha)
        self.bg_alpha_label.configure(text=str(self.settings.bg_alpha))

    def _load_fonts(self):
        names = fonts.enumerate_fonts()
        self.font_names = names
        default = _best_default_font(names)
        for _key, _label, style in self.settings.element_list():
            if not style.font or style.font not in names:
                style.font = default
        try:
            self.win.after(0, self._fonts_loaded)
        except Exception:
            pass

    def _fonts_loaded(self):
        for card in self.cards.values():
            card.refresh_fonts()
        self._schedule_preview()

    # ---------------- 事件 ----------------
    def _on_ym(self):
        try:
            self.year = int(self.year_combo.get())
            self.month = int(self.month_combo.get())
        except ValueError:
            return
        self.year = max(2000, min(2099, self.year))
        self.month = max(1, min(12, self.month))
        self._schedule_preview()

    def _go_current(self):
        y, m = default_year_month()
        self.year, self.month = y, m
        self.year_combo.set(str(y))
        self.month_combo.set(str(m))
        self._schedule_preview()

    def _on_orientation(self, val):
        self.settings.orientation = "landscape" if val == "横向" else "portrait"
        self._schedule_preview()
        self._schedule_save()

    def _on_style_change(self):
        self.settings.watermark_enabled = bool(self.wm_chk.get())
        self.settings.watermark_alpha = int(round(self.wm_alpha.get()))
        self.wm_alpha_label.configure(text=str(self.settings.watermark_alpha))
        self.settings.bg_alpha = int(round(self.bg_alpha.get()))
        self.bg_alpha_label.configure(text=str(self.settings.bg_alpha))
        self._schedule_preview()
        self._schedule_save()

    def _schedule_save(self):
        if self._save_job:
            self.win.after_cancel(self._save_job)
        self._save_job = self.win.after(600, self._do_save)

    def _do_save(self):
        save_settings(self.settings)
        self._save_job = None

    def _schedule_preview(self):
        if self._preview_job:
            self.win.after_cancel(self._preview_job)
        self._preview_job = self.win.after(250, self._render_preview)

    def _render_preview(self):
        self._preview_job = None
        try:
            # 预览用较低 DPI 提速，最终导出用 300 DPI
            img = renderer.render_calendar(self.year, self.month, self.settings, dpi=120)
        except Exception as e:
            self.preview_label.configure(text="预览失败：%s" % e, image=None)
            return
        self._preview_img = img
        self._update_preview_scale()

    def _preview_viewport(self):
        w = self.preview_scroll.winfo_width() - 24
        h = self.preview_scroll.winfo_height() - 24
        if w < 80:
            w = self.right.winfo_width() - 40
        if h < 80:
            h = self.right.winfo_height() - 90
        if w < 80:
            w = 760
        if h < 80:
            h = 520
        return w, h

    def _update_preview_scale(self):
        if self._preview_img is None:
            return
        img = self._preview_img
        iw, ih = img.size
        w, h = self._preview_viewport()
        fit = min(w / iw, h / ih)
        scale = fit * self._zoom
        dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(dw, dh))
        self._preview_img_ref = ctk_img
        self.preview_label.configure(image=ctk_img, text="")
        if abs(self._zoom - 1.0) < 1e-6:
            self.zoom_label.configure(text="适应")
        else:
            self.zoom_label.configure(text="%d%%" % int(round(self._zoom * 100)))

    def _preview_fit(self):
        self._zoom = 1.0
        self._update_preview_scale()

    def _preview_zoom_in(self):
        self._zoom = min(8.0, self._zoom * 1.25)
        self._update_preview_scale()

    def _preview_zoom_out(self):
        self._zoom = max(0.5, self._zoom / 1.25)
        self._update_preview_scale()

    def _on_preview_resize(self, event=None):
        if self._resize_job:
            self.win.after_cancel(self._resize_job)
        self._resize_job = self.win.after(120, self._update_preview_scale)

    # ---------------- 导出 ----------------
    def _base_filename(self):
        return "%d年%d月月历纸" % (self.year, self.month)

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            title="导出 PDF", defaultextension=".pdf",
            initialfile=self._base_filename() + ".pdf",
            filetypes=[("PDF 文件", "*.pdf")])
        if not path:
            return
        try:
            img = renderer.render_calendar(self.year, self.month, self.settings, dpi=300)
            img.save(path, "PDF", resolution=300.0)
            messagebox.showinfo("导出成功", "已导出：\n" + path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _export_image(self, fmt):
        ext = fmt
        path = filedialog.asksaveasfilename(
            title="导出图片", defaultextension="." + ext,
            initialfile=self._base_filename() + "." + ext,
            filetypes=[("%s 图片" % fmt.upper(), "*." + ext)])
        if not path:
            return
        try:
            img = renderer.render_calendar(self.year, self.month, self.settings, dpi=300)
            if fmt == "jpg":
                img.save(path, "JPEG", quality=95, dpi=(300, 300))
            else:
                img.save(path, "PNG", dpi=(300, 300))
            messagebox.showinfo("导出成功", "已导出：\n" + path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _choose_bg(self):
        path = filedialog.askopenfilename(
            title="选择背景图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")])
        if path:
            self.settings.bg_image = path
            self._sync_bg()
            self._schedule_preview()
            self._schedule_save()

    def _clear_bg(self):
        self.settings.bg_image = ""
        self._sync_bg()
        self._schedule_preview()
        self._schedule_save()

    def _reset_defaults(self):
        self.settings = Settings()
        names = self.font_names
        if names:
            d = _best_default_font(names)
            for _key, _label, st in self.settings.element_list():
                st.font = d
        for card in self.cards.values():
            card.style = getattr(self.settings, card.key)
            card.refresh_fonts()
        self._sync_wm()
        self._sync_bg()
        self.ori_seg.set("横向" if self.settings.orientation == "landscape" else "纵向")
        self._schedule_preview()
        self._schedule_save()

    def _on_close(self):
        self._do_save()
        self.win.destroy()

    def run(self):
        self.win.mainloop()
