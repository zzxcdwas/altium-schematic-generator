# -*- coding: utf-8 -*-
"""第三方引脚贴合校验 (altium-monkey 读磁盘文件).

monkey 独立解出每个引脚的热点 connection_point 与每条导线折线,
用来回答一个问题: 我算的热点坐标, 与 Altium 真正认的热点, 是不是同一个点?

判据取自 AD16 自带样例 (Documents/Examples/**): 在真实 AD 保存的文件里,
connection_point 100% 落在导线上, 而 location (引脚体端) 从不落在导线上——
所以 connection_point 就是电气连接点。

在最终成品里, 除"教材本来就悬空"的引脚外, 其余引脚的热点都必须落在导线上。

用法: _ampins.py
"""
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(os.path.dirname(HERE), "out")

# 教材里本来就悬空的引脚 (照图4-75: 数码管 DP 由排阻第 8 只电阻驱动,
# 无悬空; 图4-74 无悬空). 目前两图都不应有例外。
ALLOWED_OPEN = set()

CASES = [
    ("lab1", "AT89C51_图4-74_多谐振荡器.SchDoc", 1030),
    ("lab2", "Chap4-2_图4-75_数码管译码.SchDoc", 1060),
]


def on(p, a, b, tol=0.6):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return abs(px - ax) <= tol and abs(py - ay) <= tol
    t = ((px - ax) * dx + (py - ay) * dy) / float(L2)
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= tol * tol


def main():
    from altium_monkey import AltiumSchDoc

    lines = []
    bad = 0
    for cid, name, flip in CASES:
        path = os.path.join(OUT, name)
        sd = AltiumSchDoc(path)
        segs = []
        for w in sd.get_wires():
            pts = [(p.x, p.y) for p in w.points]
            for i in range(len(pts) - 1):
                segs.append((pts[i], pts[i + 1]))

        pins = sd.get_all_pins()
        hits, miss = 0, []
        for p in pins:
            cp = tuple(p.connection_point)
            if any(on(cp, a, b) for a, b in segs):
                hits += 1
            else:
                key = "%s.%s" % (p.component_designator, p.designator)
                miss.append((key, cp, (cp[0], flip - cp[1])))

        lines.append("### %s  (%s)" % (cid, name))
        lines.append("  导线段 %d / 引脚 %d" % (len(segs), len(pins)))
        lines.append("  热点落在导线上: %d / %d" % (hits, len(pins)))
        for key, cp, dsg in miss:
            if key in ALLOWED_OPEN:
                lines.append("  (允许悬空) %s" % key)
                continue
            lines.append("  !! 未接: %-8s 文件坐标%s  设计坐标%s" % (key, cp, dsg))
            bad += 1
        if not [m for m in miss if m[0] not in ALLOWED_OPEN]:
            lines.append("  OK 全部引脚均落在导线上")
        lines.append("")

    text = "\n".join(lines)
    print(text)
    open(os.path.join(OUT, "_ampins.txt"), "w", encoding="utf-8").write(text)
    print("未连接引脚: %d" % bad)
    return bad


sys.exit(0 if main() == 0 else 1)
