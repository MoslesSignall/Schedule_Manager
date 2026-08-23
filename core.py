# -*- coding: utf-8 -*-
"""月历纸生成器 —— 核心日期/农历/节日逻辑。

周次规则（按需求）：
    - 星期一为一周的开始；
    - 某年的 1 月 1 日所在的星期记作该年的第 1 个星期。
"""
from __future__ import annotations

import calendar
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# 打包后 vendor 目录不存在，开发时把 vendor 提前加入路径
try:
    import cnlunar
except ImportError:  # pragma: no cover
    _vendor = __file__ and __file__.rsplit("\\", 2)[0] + "\\vendor"
    sys.path.insert(0, _vendor)
    import cnlunar

# 月份英文简写（9 月用 SEP 表示）
MONTH_ABBR = [
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

# 农历月份中文名（初一当天用于标示月首）
LUNAR_MONTH_CN = {
    1: "正月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "冬月", 12: "腊月",
}

# 公历（阳历）固定日期节日
GREGORIAN_FESTIVALS = {
    (1, 1): "元旦",
    (3, 8): "妇女节",
    (3, 12): "植树节",
    (5, 1): "劳动节",
    (5, 4): "青年节",
    (6, 1): "儿童节",
    (7, 1): "建党节",
    (8, 1): "建军节",
    (9, 10): "教师节",
    (10, 1): "国庆节",
}

# 农历（阴历）节日  (农历月, 农历日)
LUNAR_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (2, 2): "龙抬头",
    (5, 5): "端午节",
    (7, 7): "七夕节",
    (7, 15): "中元节",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
    (12, 23): "小年",
}


def week_of_year(d: date, anchor_year: int) -> int:
    """返回 d 所在的周在 anchor_year 里的周次。

    第 1 周 = 包含 1 月 1 日的那一周；星期一为一周开始。
    """
    jan1 = date(anchor_year, 1, 1)
    week1_monday = jan1 - timedelta(days=jan1.weekday())
    monday = d - timedelta(days=d.weekday())
    return (monday - week1_monday).days // 7 + 1


@dataclass
class DayInfo:
    day: int                    # 公历日 1..31
    weekday: int                # 0=周一 .. 6=周日
    lunar_text: str             # 农历文本（如“十六”，初一为月份名）
    festival: str               # 节气/节日名，无则为空串
    secondary_text: str         # 单元格中要显示的第二段文本
    secondary_kind: str         # "lunar" 或 "festival"


@dataclass
class WeekRow:
    week_label: str             # 周次文本，如 "27"
    days: list                  # 长度 7，元素为 DayInfo 或 None
    week_label2: str = ""       # 一行合并两周时，第二个周次文本（如 "36"）；否则为空


def _lunar_day_name(ld: int) -> str:
    """农历日名：初一..三十。"""
    day_names = ["初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
                 "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "廿",
                 "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "卅"]
    if 1 <= ld <= 30:
        return day_names[ld - 1]
    return ""


def _lunar_month_name(lm: int, is_leap: bool) -> str:
    prefix = "闰" if is_leap else ""
    return prefix + LUNAR_MONTH_CN.get(lm, str(lm) + "月")


def _is_chuxi(d: date) -> bool:
    """判断是否为除夕（次日即春节 / 农历正月初一）。"""
    tomorrow = d + timedelta(days=1)
    tl = cnlunar.Lunar(datetime(tomorrow.year, tomorrow.month, tomorrow.day), godType="8char")
    return (tl.lunarMonth == 1 and tl.lunarDay == 1 and not tl.isLunarLeapMonth)


def _floating_festival(d: date) -> str:
    """浮动公历节日：母亲节（5 月第二个周日）、父亲节（6 月第三个周日）。"""
    if d.month == 5 and d.weekday() == 6 and 8 <= d.day <= 14:
        return "母亲节"
    if d.month == 6 and d.weekday() == 6 and 15 <= d.day <= 21:
        return "父亲节"
    return ""


def _get_festival(d: date, lunar) -> str:
    """返回该日的节气/节日名（节气优先，其次节日），无则空串。"""
    term = lunar.todaySolarTerms
    if term and term != "无":
        return term
    key = (d.month, d.day)
    if key in GREGORIAN_FESTIVALS:
        return GREGORIAN_FESTIVALS[key]
    if not lunar.isLunarLeapMonth:
        lk = (lunar.lunarMonth, lunar.lunarDay)
        if lk in LUNAR_FESTIVALS:
            return LUNAR_FESTIVALS[lk]
    fl = _floating_festival(d)
    if fl:
        return fl
    if _is_chuxi(d):
        return "除夕"
    return ""


def build_day(d: date) -> DayInfo:
    lunar = cnlunar.Lunar(datetime(d.year, d.month, d.day), godType="8char")
    lm, ld = lunar.lunarMonth, lunar.lunarDay
    is_leap = bool(lunar.isLunarLeapMonth)

    if ld == 1:
        lunar_text = _lunar_month_name(lm, is_leap)
    else:
        lunar_text = _lunar_day_name(ld)

    festival = _get_festival(d, lunar)
    if festival:
        secondary_text, secondary_kind = festival, "festival"
    else:
        secondary_text, secondary_kind = lunar_text, "lunar"

    return DayInfo(
        day=d.day,
        weekday=d.weekday(),
        lunar_text=lunar_text,
        festival=festival,
        secondary_text=secondary_text,
        secondary_kind=secondary_kind,
    )


def build_month(year: int, month: int) -> list[WeekRow]:
    """构建某个月的 5 行周数据（7 行 × 8 列表格中的 3~7 行）。"""
    first = date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    start_wd = first.weekday()

    num_weeks = (start_wd + days_in_month + 6) // 7  # 该月跨越的周数

    monday = first - timedelta(days=start_wd)
    weeks: list[WeekRow] = []
    for _ in range(num_weeks):
        cells = []
        for i in range(7):
            d = monday + timedelta(days=i)
            if d.year == year and d.month == month:
                cells.append(build_day(d))
            else:
                cells.append(None)
        label = str(week_of_year(monday, year))
        weeks.append(WeekRow(week_label=label, days=cells))
        monday += timedelta(days=7)

    if num_weeks == 6:
        # 把第 1 周与第 6 周合并到同一行（二者工作日列互不重叠），行首存两个周次
        first_row, last_row = weeks[0], weeks[-1]
        merged = [first_row.days[i] if first_row.days[i] is not None else last_row.days[i]
                  for i in range(7)]
        return [WeekRow(week_label=first_row.week_label,
                        week_label2=last_row.week_label,
                        days=merged)] + weeks[1:5]

    if num_weeks == 4:
        # 平年 2 月（1 日为周一）只有 4 周，第 5 行留空
        empty = WeekRow(week_label="", days=[None] * 7)
        return weeks + [empty]

    return weeks
