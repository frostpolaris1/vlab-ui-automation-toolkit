# -*- coding: utf-8 -*-
"""从大视图截图读取钢直尺刻度与被测物边缘（像素法，只读分析）。

用法: py -3 -I measure_ruler_pixels.py <screenshot.png> [--row-tick Y] [--row-object Y]
输出: 刻度主刻度 x 坐标/px_per_cm；物体左右边缘 x；长度 cm/mm。
"""
import sys
from PIL import Image


def brightness(p):
    return (p[0] + p[1] + p[2]) / 3.0


def dark_runs(img, y, x0, x1, thresh=110):
    """返回该行暗像素连续段 [(start,end)]。"""
    runs = []
    in_run = False
    start = 0
    for x in range(x0, x1):
        b = brightness(img.getpixel((x, y)))
        if b < thresh:
            if not in_run:
                in_run = True
                start = x
        else:
            if in_run:
                runs.append((start, x - 1))
                in_run = False
    if in_run:
        runs.append((start, x1 - 1))
    return runs


def main():
    path = sys.argv[1]
    img = Image.open(path).convert("RGB")
    w, h = img.size
    print("size", w, h)

    # 1) 刻度行：在 y=570..600 找暗像素数量最多的行
    best = None
    for y in range(540, 620):
        runs = dark_runs(img, y, 280, 1390)
        n = sum(e - s + 1 for s, e in runs)
        if best is None or n > best[1]:
            best = (y, n, len(runs))
    print("tick row best", best)
    ty = best[0]
    runs = dark_runs(img, ty, 280, 1390)
    # 合并相邻像素（抗锯齿）
    print("runs at y=%d count=%d" % (ty, len(runs)))
    centers = [(s + e) / 2.0 for s, e in runs]
    print("centers:", ["%.1f" % c for c in centers])

    # 2) 刻度高度：统计每列暗像素纵向长度（区分主/次刻度）
    heights = {}
    for cx in centers:
        x = int(round(cx))
        cnt = 0
        for yy in range(ty - 25, ty + 25):
            if 0 <= yy < h and brightness(img.getpixel((x, yy))) < 110:
                cnt += 1
        heights[x] = cnt
    print("heights:", heights)

    # 3) 物体边缘：在刻度上方 y 行扫描亮度突变（物体金属灰 vs 背景）
    for oy in (500, 510, 520, 530, 620, 630):
        row = [brightness(img.getpixel((x, oy))) for x in range(300, 1390)]
        # 找长平台段（物体）
        vals = []
        for i, b in enumerate(row):
            vals.append((300 + i, b))
        # 检测与背景(≈182-190)差异大的连续段
        seg = [x for x, b in vals if b < 170]
        if seg:
            # 连续段
            groups = []
            s = seg[0]
            p = seg[0]
            for x in seg[1:]:
                if x - p > 5:
                    groups.append((s, p))
                    s = x
                p = x
            groups.append((s, p))
            groups = [g for g in groups if g[1] - g[0] > 200]
            print("oy=%d dark-ish groups:" % oy, groups)
            for g in groups:
                print("   width px=%d" % (g[1] - g[0]))

    # 4) 更精细：打印 oy 行 500..560 区间亮度分段
    for oy in (500, 520, 540):
        prev = None
        edges = []
        for x in range(480, 1200):
            b = brightness(img.getpixel((x, oy)))
            cls = 0 if b < 150 else 1
            if prev is None:
                prev = cls
            elif cls != prev:
                edges.append(x)
                prev = cls
        print("oy=%d edges:" % oy, edges)


if __name__ == "__main__":
    main()
