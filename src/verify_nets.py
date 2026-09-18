# -*- coding: utf-8 -*-
"""独立网表复算: 用 altium-monkey 解析 .SchDoc 的引脚与导线, 自己重新做
并查集连通, 再把结果与 build_lab 的意图网表逐网比对。

这是对"几何审计 (只校验我自己算的坐标)" 的第三方补充:
monkey 读的是磁盘上的真实文件, 引脚坐标/导线坐标都不经过我的代码。

用法: _amnets.py
"""
from __future__ import print_function

import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT = os.path.join(os.path.dirname(HERE), "out")
TOL = 0.6


# --------------------------------------------------------------- union-find
class DSU(object):
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _on_seg(p, a, b, tol=TOL):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return abs(px - ax) <= tol and abs(py - ay) <= tol
    t = ((px - ax) * dx + (py - ay) * dy) / float(L2)
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= tol * tol


def wire_points(w):
    """altium-monkey wire -> [(x, y), ...] (already in design coords)."""
    pts = []
    v = getattr(w, "points", None)
    if v:
        for q in v:
            if hasattr(q, "x"):
                pts.append((float(q.x), float(q.y)))
            elif isinstance(q, (list, tuple)) and len(q) >= 2:
                pts.append((float(q[0]), float(q[1])))
    return pts


def main():
    import altium_monkey
    import build_lab

    cases = [("lab1", build_lab.build_lab1,
              os.path.join(OUT, "AT89C51_图4-74_多谐振荡器.SchDoc")),
             ("lab2", build_lab.build_lab2,
              os.path.join(OUT, "Chap4-2_图4-75_数码管译码.SchDoc"))]

    report = []
    bad = 0
    for cid, fn, doc in cases:
        report.append("=" * 72)
        report.append("### %s   %s" % (cid, os.path.basename(doc)))
        sd = altium_monkey.AltiumSchDoc(doc)

        # -- 1. pins straight out of the file ---------------------------
        pins = []
        for p in sd.get_all_pins():
            cp = tuple(p.connection_point)
            pins.append(("%s.%s" % (p.component_designator, p.designator), cp))
        report.append("  pins parsed      : %d" % len(pins))

        # -- 2. wires ---------------------------------------------------
        wires = []
        for w in sd.get_wires():
            pts = wire_points(w)
            for i in range(len(pts) - 1):
                wires.append((pts[i], pts[i + 1]))
        report.append("  wire segments    : %d" % len(wires))

        # -- 3. rebuild connectivity ------------------------------------
        dsu = DSU()
        # every node keyed by coordinate so identical points merge
        for i, (a, b) in enumerate(wires):
            dsu.union(("p", a), ("p", b))
        # T-connections: an endpoint landing inside another segment
        for a, b in wires:
            for pt in (a, b):
                for c, d in wires:
                    if (c, d) == (a, b):
                        continue
                    if _on_seg(pt, c, d):
                        dsu.union(("p", pt), ("p", c))
        # pins join the wire they touch
        for key, cp in pins:
            dsu.union(("pin", key), ("p", cp))
            for c, d in wires:
                if _on_seg(cp, c, d):
                    dsu.union(("pin", key), ("p", c))
                    break

        # power ports: Altium merges every port of the same name into one net,
        # so GND (three symbols) / VCC (two symbols) must be unified by text.
        ports = sd.get_power_ports()
        for q in ports:
            cp = tuple(q.connection_point)
            dsu.union(("net", q.text.upper()), ("p", cp))
            for c, d in wires:
                if _on_seg(cp, c, d):
                    dsu.union(("net", q.text.upper()), ("p", c))
                    break
        # net labels do the same job for named signals
        for lb in sd.get_net_labels():
            nm = getattr(lb, "text", None)
            if not nm:
                continue
            cp = tuple(getattr(lb, "connection_point", lb.location))
            dsu.union(("net", nm.upper()), ("p", cp))
            for c, d in wires:
                if _on_seg(cp, c, d):
                    dsu.union(("net", nm.upper()), ("p", c))
                    break

        # -- 4. group pins into nets -------------------------------------
        groups = defaultdict(list)
        for key, cp in pins:
            groups[dsu.find(("pin", key))].append(key)
        got = set()
        for root, members in groups.items():
            if len(members) > 1:
                got.add(frozenset(members))

        # -- 5. intended netlist, in the same "REF.PIN" form -------------
        want = set()
        sch = fn()
        for name, plist in sch.nets.items():
            members = frozenset("%s.%s" % (r, d) for r, d in plist)
            if len(members) > 1:
                want.add(members)

        missing = sorted(want - got)
        extra = sorted(got - want)
        report.append("  意图网(>=2脚)   : %d" % len(want))
        report.append("  复算网(>=2脚)   : %d" % len(got))
        if missing:
            report.append("  !! 复算缺失:")
            for m in missing:
                report.append("     " + " ".join(sorted(m)))
            bad += len(missing)
        if extra:
            report.append("  !! 复算多出 (可能短路):")
            for m in extra:
                report.append("     " + " ".join(sorted(m)))
            bad += len(extra)
        if not missing and not extra:
            report.append("  OK 网表完全一致 (第三方解析器独立复算)")

    text = "\n".join(report)
    print(text)
    open(os.path.join(OUT, "_amnets.txt"), "w", encoding="utf-8").write(text)
    print("\n不一致条目: %d" % bad)
    return bad


sys.exit(0 if main() == 0 else 1)
