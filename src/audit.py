# -*- coding: utf-8 -*-
"""几何审计: 悬空引脚 / 异网导线相碰 / 导线穿越异网引脚"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "_geoaudit.txt")

TOL = 1.5

def seg_endpoints(poly):
    return [poly[0], poly[-1]]

def point_on_seg(p, a, b, tol=TOL):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return abs(px - ax) <= tol and abs(py - ay) <= tol
    # 距离
    L2 = dx * dx + dy * dy
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= tol * tol

def on_body_only(p, a, b, tol=TOL):
    """p 在线段内部(非端点)"""
    return point_on_seg(p, a, b, tol) and p != a and p != b

def audit(sch, name, lines):
    lines.append("### %s" % name)
    # 收集 wire 端点与线段
    segs = []   # (net, a, b)
    for net, polys in sch.net_wires.items():
        for poly in polys:
            for i in range(len(poly) - 1):
                segs.append((net, poly[i], poly[i + 1]))
    verts = []  # 所有拐点 (net, point) -- 拐点落在异网线段上也算短路
    for net, polys in sch.net_wires.items():
        for poly in polys:
            for p in poly:
                verts.append((net, tuple(p)))

    errors = []
    # 1. 引脚覆盖检查
    for part in sch.parts:
        for d, pin in part.pins.items():
            p = (pin["x"], pin["y"])
            covered_by = []
            for net, pt in verts:
                if abs(pt[0] - p[0]) <= TOL and abs(pt[1] - p[1]) <= TOL:
                    covered_by.append(net)
            for net, a, b in segs:
                if point_on_seg(p, a, b, TOL):
                    covered_by.append(net)
            if not covered_by:
                errors.append("FLOATING %s.%s @(%d,%d) net=%s" % (part.ref, d, p[0], p[1], part_pin_net(sch, part.ref, d)))
            else:
                bad = set(covered_by) - {part_pin_net(sch, part.ref, d)}
                if bad:
                    errors.append("PIN-SHORT %s.%s @(%d,%d) 应属 %s 但被 %s 覆盖"
                                  % (part.ref, d, p[0], p[1], part_pin_net(sch, part.ref, d), sorted(bad)))
    # 2. 导线互相触碰: 异网拐点落在线段上 / 共线重叠
    for i, (n1, pt) in enumerate(verts):
        for j, (n2, a, b) in enumerate(segs):
            if n1 == n2:
                continue
            if point_on_seg(pt, a, b, TOL):
                errors.append("WIRE-SHORT %s 拐点(%d,%d) 落在 %s 线段 (%s)-(%s)"
                              % (n1, pt[0], pt[1], n2, a, b))
    # 共线重叠 (同向线段重叠区间, 不同网)
    def _collinear_overlap(s1, s2):
        (n1, a1, b1), (n2, a2, b2) = s1, s2
        for (p, q) in ((a1, b1), (b1, a1)):
            for (r, s) in ((a2, b2), (b2, a2)):
                # 方向一致且起点共线
                d1 = (q[0] - p[0], q[1] - p[1])
                d2 = (s[0] - r[0], s[1] - r[1])
                if d1[0] * d2[1] - d1[1] * d2[0] != 0:
                    continue
                # r 在 p->q 线上
                cross = (r[0] - p[0]) * d1[1] - (r[1] - p[1]) * d1[0]
                if cross != 0:
                    continue
                t1 = ((r[0] - p[0]) * d1[0] + (r[1] - p[1]) * d1[1])
                t2 = ((s[0] - p[0]) * d1[0] + (s[1] - p[1]) * d1[1])
                L = d1[0] * d1[0] + d1[1] * d1[1]
                lo, hi = sorted((min(t1, t2) / L, max(t1, t2) / L))
                if lo < 1 and hi > 0:
                    return True
        return False
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][0] == segs[j][0]:
                continue
            if _collinear_overlap(segs[i], segs[j]):
                errors.append("COLLINEAR-OVERLAP %s %s 与 %s %s 重叠"
                              % (segs[i][0], segs[i][1:], segs[j][0], segs[j][1:]))
    # 3. 中段十字交叉 (Altium 不导通, 但图面像接了线 -> 必须报告)
    def _cross_point(s1, s2):
        (n1, a1, b1), (n2, a2, b2) = s1, s2
        d1x, d1y = b1[0] - a1[0], b1[1] - a1[1]
        d2x, d2y = b2[0] - a2[0], b2[1] - a2[1]
        den = d1x * d2y - d1y * d2x
        if den == 0:
            return None
        t = ((a2[0] - a1[0]) * d2y - (a2[1] - a1[1]) * d2x) / float(den)
        u = ((a2[0] - a1[0]) * d1y - (a2[1] - a1[1]) * d1x) / float(den)
        eps = 1e-6
        if not (-eps <= t <= 1 + eps and -eps <= u <= 1 + eps):
            return None
        # 端点相触由第 2 步负责, 这里只报真正的"中段-中段"穿孔
        if t <= eps or t >= 1 - eps or u <= eps or u >= 1 - eps:
            return None
        return (a1[0] + d1x * t, a1[1] + d1y * t)

    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][0] == segs[j][0]:
                continue
            p = _cross_point(segs[i], segs[j])
            if p:
                errors.append("WIRE-CROSS %s %s 中段穿过 %s %s @(%d,%d)"
                              % (segs[i][0], segs[i][1:], segs[j][0], segs[j][1:],
                                 p[0], p[1]))
    lines.append("\n".join(errors) if errors else "(无几何错误)")
    lines.append("")
    return len(errors)

def part_pin_net(sch, ref, d):
    for net, pins in sch.nets.items():
        for r, dd in pins:
            if r == ref and str(dd) == str(d):
                return net
    return "?"

def main():
    lines = []
    try:
        import build_lab
        for cid, fn in (("lab1", build_lab.build_lab1), ("lab2", build_lab.build_lab2)):
            sch = fn()
            audit(sch, cid, lines)
    except Exception:
        lines.append("ERROR:\n" + traceback.format_exc())
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))

main()
