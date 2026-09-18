# -*- coding: utf-8 -*-
"""图7-12 层次化设计第三方校验 (altium-monkey 读磁盘文件).

A. 每张子图: 所有引脚热点落在导线上 (同 _ampins 判据)
B. 每张子图: RECORD=18 端口的连接点落在导线上
C. 顶层: 每个图纸符号入口的连接点落在顶层导线上
D. 跨图对应: S1/S2 的端口名集合 == 顶层对应符号的入口名集合

所有坐标为文件坐标 (y-up); 设计坐标 = flip - file_y (flip=图高)。
"""
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "out")

CASES = [
    ("Oscillator.SchDoc", 480),
    ("S1.SchDoc", 470),
    ("S2.SchDoc", 380),
    ("Top_Level.SchDoc", 260),
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

    wire_segs = {}
    for name, flip in CASES:
        sd = AltiumSchDoc(os.path.join(OUT, name))
        segs = []
        for w in sd.get_wires():
            pts = [(p.x, p.y) for p in w.points]
            for i in range(len(pts) - 1):
                segs.append((pts[i], pts[i + 1]))
        wire_segs[name] = segs

        lines.append("### %s  (flip=%d)" % (name, flip))
        # ---- A. 引脚 ----
        pins = sd.get_all_pins()
        hits, miss = 0, []
        for p in pins:
            cp = tuple(p.connection_point)
            if any(on(cp, a, b) for a, b in segs):
                hits += 1
            else:
                miss.append("%s.%s@%s" % (p.component_designator, p.designator, cp))
        lines.append("  A. 引脚落线: %d / %d%s" % (hits, len(pins),
                     ("" if not miss else "  !! 未接: " + ", ".join(miss))))
        bad += len(miss)

        # ---- B. 端口 (R18) ----
        ports = sd.get_ports()
        pbad = 0
        for p in ports:
            name_p = getattr(p.record, "name", "?")
            cps = [tuple(c) for c in p.connection_points]
            ok = [any(on(cp, a, b) for a, b in segs) for cp in cps]
            if not any(ok):
                lines.append("  !! 端口 %s 连接点 %s 均未落线" % (name_p, cps))
                pbad += 1
        lines.append("  B. 端口落线: %d / %d" % (len(ports) - pbad, len(ports)))
        bad += pbad
        lines.append("")

    # ---- C. 顶层入口落线 ----
    from altium_monkey import AltiumSchDoc as ASD
    sd = ASD(os.path.join(OUT, "Top_Level.SchDoc"))
    segs = wire_segs["Top_Level.SchDoc"]
    lines.append("### Top_Level.SchDoc 图纸符号入口")
    sym_bad = 0
    sym_ports = {}
    sym_points = {}
    for s in sd.get_sheet_symbols():
        rec = s.record
        nm = str(getattr(rec.sheet_name, "text", rec.sheet_name))
        loc = rec.location
        xs = int(rec.x_size)
        sym_ports[nm] = []
        sym_points[nm] = []
        for e in s.entries:
            en = e.name
            side = int(e.side)
            dist = int(e.distance_from_top)
            if side == 1:
                cp = (loc.x + xs, loc.y - dist * 10)
            elif side == 0:
                cp = (loc.x, loc.y - dist * 10)
            else:
                cp = (loc.x + dist * 10, loc.y)
            hit = any(on(cp, a, b) for a, b in segs)
            sym_ports[nm].append(en)
            sym_points[nm].append((cp[0], 260 - cp[1]))
            if not hit:
                lines.append("  !! 符号 %s 入口 %s 连接点 %s 未落线 (side=%d dist=%d)"
                             % (nm, en, cp, side, dist))
                sym_bad += 1
        lines.append("  符号 %-3s 入口 %-12s 设计空间入口点 %s"
                     % (nm, ",".join(sorted(sym_ports[nm])), sym_points[nm]))
    lines.append("  C. 入口落线: %s" % ("全部通过" if sym_bad == 0 else "%d 处未落线" % sym_bad))
    bad += sym_bad

    # ---- D. 跨图名称对应 ----
    lines.append("")
    lines.append("### D. 端口/入口名称对应")
    port_names = {}
    for sheet in ("S1.SchDoc", "S2.SchDoc"):
        sdd = ASD(os.path.join(OUT, sheet))
        port_names[sheet] = sorted(p.record.name for p in sdd.get_ports())
    sym1 = sorted(sym_ports.get("S1", []))
    sym2 = sorted(sym_ports.get("S2", []))
    lines.append("  S1 端口 %s  <->  顶层 S1 符号入口 %s  -> %s"
                 % (port_names["S1.SchDoc"], sym1,
                    "一致" if port_names["S1.SchDoc"] == sym1 else "不一致 !!"))
    lines.append("  S2 端口 %s  <->  顶层 S2 符号入口 %s  -> %s"
                 % (port_names["S2.SchDoc"], sym2,
                    "一致" if port_names["S2.SchDoc"] == sym2 else "不一致 !!"))
    if port_names["S1.SchDoc"] != sym1:
        bad += 1
    if port_names["S2.SchDoc"] != sym2:
        bad += 1

    text = "\n".join(lines)
    print(text)
    open(os.path.join(OUT, "_hierverify.txt"), "w", encoding="utf-8").write(text)
    print("问题总数: %d" % bad)
    return bad


sys.exit(0 if main() == 0 else 1)
