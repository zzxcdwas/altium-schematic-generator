# -*- coding: utf-8 -*-
"""Generate the two textbook-practice schematics, laid out 1:1 with the photos.

v14 -- every component is now an OFFICIAL LIBRARY SYMBOL (user requirement:
       "元器件不要你自己画，你给我从库里找").  No hand-drawn symbol bodies remain.

  图4-74  多谐振荡器
     RES       [01-电阻-电容-电感.SchLib]      锯齿电阻 (教材样式) x8
     Cap       [Miscellaneous Devices.IntLib]  200pF x4
     Diode     [02-二极管-整流桥.SchLib]       1N914 x2
     9013-DIP  [04-三极管.SchLib]              2N3904 x2
     Header 2  [Miscellaneous Connectors]      P1
  图4-75  数码管译码
     74LS47    [14-74系列TTL芯片.SchLib]       SN7447AN x2  (图形在 DISPLAYMODE=1)
     Res Pack3 [Miscellaneous Devices.IntLib]  x2  (左 1-8 / 右 16-9, 与教材一致)
     Dpy Blue-CA [Miscellaneous Devices.IntLib] x2 (左 7,6,4,2,1,9,10,5 / 右 3,8)
     Header 2 / Header 8 / Cap

Per-pin library geometry was measured, not guessed -- see out/_parts.txt.
Every wire endpoint is taken from part.hotspot() so it cannot miss a pin.
Direction codes: 0=+x 1=+y 2=-x 3=-y in the y-down design space used here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                        # 示例自身
sys.path.insert(0, os.path.join(ROOT, "src"))   # 核心库

import schlib
import sch_build
import erc

RCL = "01-电阻-电容-电感.SchLib"
DIO = "02-二极管-整流桥.SchLib"
TRI = "04-三极管.SchLib"
TTL = "14-74系列TTL芯片.SchLib"
DEV = "Miscellaneous Devices.IntLib"
CON = "Miscellaneous Connectors.IntLib"


def _X(part, pin):
    return part.hotspot(pin)["x"]


def _Y(part, pin):
    return part.hotspot(pin)["y"]


def _P(part, pin):
    """Absolute hot-spot of a placed pin -- never hand-compute wire ends."""
    h = part.hotspot(pin)
    return (h["x"], h["y"])


def _quiet(sch, show_desig=()):
    """Textbook style: no pin names anywhere, designators only where noted."""
    for part in sch.parts:
        part.symbol.show_pin_names = False
        part.symbol.show_pin_designators = False
    for part in show_desig:
        part.symbol.show_pin_designators = True


# ------------------------------------------------------------------- lab1 --
def build_lab1():
    """图4-74 实践题(1): 2N3904 多谐振荡器 (照教材照片版式).

    列 (关于 x=700 对称): R5=120 | R1/Q1/C1 列=380 | D1=500 | R7=620
                          R8=780 | D2=900 | R2/Q2/C2 列=1020 | R6=1280
    行: VCC 轨=100 | R1/R2=140..180 | C1/C2=260 | C1 支线=300 | R3/R4=340
        交叉通道=470 | 基极行 B1/B2=550 | R7/R8=550..590 | VEE=590..615
        底部轨 K1/N1/K2=680 | P1=845..855 | GND=600/900
    """
    sch = sch_build.Schematic(1400, 1030, title="图4-74 多谐振荡器")

    # -- 器件 (全部官方库件) --------------------------------------------
    R1 = sch.place_pin("R1", "RES", RCL, "1", 380, 140, rot=270, value="1k")
    R2 = sch.place_pin("R2", "RES", RCL, "1", 1020, 140, rot=270, value="1k")
    C1 = sch.place_pin("C1", "Cap", DEV, "1", 380, 260, value="200pF")
    # C2 必须 rot=0: rot=180 会把 pin1 放到集电极竖线的「右侧」(1050,260),
    # 于是 B1 网从 (1050,260) 向左的走线正好压过 C2.2 的热点 (1020,260)
    # -> Altium 判定真实短路。rot=0 让 pin1 (900+90=990,260) 与 pin2 都落在
    # 竖线左侧, B1 的横线从 990 直接向左走, 不再穿过集电极竖线。
    C2 = sch.place_pin("C2", "Cap", DEV, "2", 1020, 260, value="200pF")
    R3 = sch.place_pin("R3", "RES", RCL, "1", 380, 340, value="39k")
    R4 = sch.place_pin("R4", "RES", RCL, "1", 1020, 340, rot=180, value="39k")
    R5 = sch.place_pin("R5", "RES", RCL, "1", 120, 300, rot=270, value="10k")
    R6 = sch.place_pin("R6", "RES", RCL, "1", 1280, 300, rot=270, value="10k")
    Q1 = sch.place_pin("Q1", "9013-DIP", TRI, "3", 380, 530, mirror=True, value="2N3904")
    Q2 = sch.place_pin("Q2", "9013-DIP", TRI, "3", 1020, 530, value="2N3904")
    R7 = sch.place_pin("R7", "RES", RCL, "1", 620, 550, rot=270, value="390k")
    R8 = sch.place_pin("R8", "RES", RCL, "1", 780, 550, rot=270, value="390k")
    D1 = sch.place_pin("D1", "Diode", DIO, "1", 500, 570, rot=270, value="1N914")
    D2 = sch.place_pin("D2", "Diode", DIO, "1", 900, 570, rot=270, value="1N914")
    C3 = sch.place_pin("C3", "Cap", DEV, "1", 560, 680, value="200pF")
    C4 = sch.place_pin("C4", "Cap", DEV, "1", 790, 680, value="200pF")
    P1 = sch.place_pin("P1", "Header 2", CON, "2", 560, 845, rot=180, value="Header 2")

    # 位号/参数照教材摆 (库件默认位置对竖直/镜像件不适用)
    for r in (R1, R2, R5, R6, R7, R8):
        r.set_text(12, 14, 12, 36)
    R3.set_text(10, -10, 10, 22)
    R4.set_text(-46, -10, -46, 22)
    C1.set_text(6, -14, 6, 22)
    C2.set_text(-40, -14, -40, 22)
    C3.set_text(6, -14, 6, 22)
    C4.set_text(6, -14, 6, 22)
    D1.set_text(-42, -14, -42, 28)
    D2.set_text(20, -14, 20, 28)
    Q1.set_text(-64, -36, -64, 62)
    Q2.set_text(26, -36, 26, 62)
    P1.set_text(-50, -16, -50, 34)

    # -- 网表 (与教材照片一致) -------------------------------------------
    sch.net("VCC", ("R1", "1"), ("R2", "1"))
    sch.net("C1", ("R1", "2"), ("C1", "1"), ("R3", "1"), ("R5", "1"), ("Q1", "3"))
    sch.net("C2", ("R2", "2"), ("C2", "2"), ("R4", "1"), ("R6", "1"), ("Q2", "3"))
    sch.net("B1", ("Q1", "2"), ("R7", "1"), ("D1", "1"), ("R4", "2"), ("C2", "1"))
    sch.net("B2", ("Q2", "2"), ("R8", "1"), ("D2", "1"), ("R3", "2"), ("C1", "2"))
    sch.net("VEE", ("R7", "2"), ("R8", "2"))
    sch.net("K1", ("R5", "2"), ("D1", "2"), ("C3", "1"))
    sch.net("K2", ("R6", "2"), ("D2", "2"), ("C4", "2"))
    sch.net("N1", ("C3", "2"), ("C4", "1"), ("P1", "2"))
    sch.net("GND", ("Q1", "1"), ("Q2", "1"), ("P1", "1"))

    colL, colR = _X(R1, "2"), _X(R2, "2")          # 380 / 1020
    xL, xR = colL + 100, colR - 100                # 480 / 920 交叉通道
    yBase = _Y(Q1, "2")                            # 550 基极行
    yLane = yBase - 80                             # 470 交叉通道行
    xa0, xa1 = xL + 80, _X(R8, "1") + 60           # 560 -> 840  左节点斜线
    xb0, xb1 = xR - 80, _X(R7, "1") - 60           # 840 -> 560  右节点斜线

    # VCC: 顶部轨 + 两端下到 R1/R2 + 中间端口
    sch.wire_net("VCC", [
        [_P(R1, "1"), (colL, 100), (colR, 100), _P(R2, "1")],
        [(700, 100), (700, 80)],
    ])
    sch.port("VCC", 700, 80, style=2, orientation=1)

    # C1/C2 网: 一条集电极竖管串起 R.C / 耦合电容 / 偏置支线 / 外接支线
    sch.wire_net("C1", [
        [_P(R1, "2"), _P(Q1, "3")],                # 180 -> 530 (沿途 3 个结点)
        [_P(R5, "1"), (colL, _Y(R5, "1"))],        # R5 支线
    ])
    sch.wire_net("C2", [
        [_P(R2, "2"), _P(Q2, "3")],
        [_P(R6, "1"), (colR, _Y(R6, "1"))],
    ])

    # B2: C1 侧节点 -> 交叉斜线 -> Q2 基极 / R8 顶 / D2 阳极
    sch.wire_net("B2", [
        [_P(C1, "2"), (xL, _Y(C1, "2")), (xL, yLane), (xa0, yLane), (xa1, yBase)],
        [_P(R3, "2"), (xL, _Y(R3, "2"))],
        [_P(R8, "1"), _P(Q2, "2")],
        [_P(D2, "1"), (_X(D2, "1"), yBase)],
    ])
    # B1: C2 侧节点 -> 交叉斜线 -> Q1 基极 / R7 顶 / D1 阳极
    sch.wire_net("B1", [
        [_P(Q1, "2"), _P(R7, "1")],
        [_P(D1, "1"), (_X(D1, "1"), yBase)],
        [_P(C2, "1"), (xR, _Y(C2, "1")), (xR, yLane), (xb0, yLane), (xb1, yBase)],
        [_P(R4, "2"), (xR, _Y(R4, "2"))],
    ])

    # VEE: R7/R8 底部汇接
    sch.wire_net("VEE", [
        [_P(R7, "2"), _P(R8, "2")],
        [(700, _Y(R7, "2")), (700, 615)],
    ])
    sch.port("VEE", 700, 615, style=2, orientation=3)

    # 底部轨: K1 - C3 - N1 - C4 - K2
    sch.wire_net("K1", [
        [_P(R5, "2"), (120, 680), _P(C3, "1")],
        [_P(D1, "2"), (_X(D1, "2"), 680)],
    ])
    sch.wire_net("K2", [
        [_P(R6, "2"), (1280, 680), _P(C4, "2")],
        [_P(D2, "2"), (_X(D2, "2"), 680)],
    ])
    sch.wire_net("N1", [
        [_P(C3, "2"), _P(C4, "1")],
        [(690, 680), (690, _Y(P1, "2")), _P(P1, "2")],
    ])

    # GND: Q1/Q2 发射极 + P1.1
    sch.wire_net("GND", [
        [_P(Q1, "1"), (_X(Q1, "1"), 600)],
        [_P(Q2, "1"), (_X(Q2, "1"), 600)],
        [_P(P1, "1"), (740, _Y(P1, "1")), (740, 900)],
    ])
    sch.port("GND", _X(Q1, "1"), 600, style=4, orientation=3)
    sch.port("GND", _X(Q2, "1"), 600, style=4, orientation=3)
    sch.port("GND", 740, 900, style=4, orientation=3)

    sch.label("C1", 200, 292)
    sch.label("C2", 1200, 292)
    sch.label("B1", 430, 542)
    sch.label("B2", 950, 542)
    sch.label("K1", 220, 672)
    sch.label("K2", 1200, 672)
    sch.label("N1", 700, 672)
    sch.note("图4-74 实践题(1): 2N3904 多谐振荡器", 100, 985)

    _quiet(sch, show_desig=(P1,))
    return sch


# ------------------------------------------------------------------- lab2 --
def _channel(sch, tag, uy):
    """一路译码通道 (照教材): 74LS47 -> Res Pack3 -> Dpy Blue-CA.

    三个库件都放在同一条 10 网格上, 原点分别为 U(400,uy) / R(660,uy) /
    DS(900,uy).  实测引脚行序与教材完全一致:
      U  左 4,5,3,7,1,2,6 + 8(GND, 底部)   右 13,12,11,10,9,15,14 + 16(VCC)
      R  左 1..8                            右 16..9
      DS 左 7,6,4,2,1,9,10,5                右 3,8 (公共阳极)
    因为 U.13..U.14 与 R.1..R.7 同 y, R.16..R.10 又与 DS.7..DS.10 同 y,
    7 条段线全是水平直线 (教材画法), 不会出现斜线。

    第 8 只电阻 (R.8 / R.9) 照教材: 左端 8 -> GND, 右端 9 -> DS.5(DP)。
    """
    U = sch.add("U" + tag, "74LS47", 400, uy, lib=TTL, value="SN7447AN")
    U.symbol.props["DISPLAYMODE"] = "1"     # 74LS47 图形全在 DM=1, DM=0 是空框
    R = sch.add("R" + tag, "Res Pack3", 660, uy, lib=DEV, value="Res Pack3")
    DS = sch.add("DS" + tag, "Dpy Blue-CA", 900, uy, lib=DEV, value="Dpy Blue-CA")
    for p in (U, R, DS):
        p.symbol.label_above = True
    _quiet(sch)
    for p in (U, R, DS):
        p.symbol.show_pin_designators = True

    # 段链: (U 输出脚, R 左列脚, R 右列脚, DS 左列脚)
    segs = [("13", "1", "16", "7"), ("12", "2", "15", "6"), ("11", "3", "14", "4"),
            ("10", "4", "13", "2"), ("9", "5", "12", "1"), ("15", "6", "11", "9"),
            ("14", "7", "10", "10")]
    for k, (upin, lpin, rpin, dpin) in enumerate(segs):
        n1 = "S%s_%d" % (tag, k)
        sch.net(n1, ("U" + tag, upin), ("R" + tag, lpin))
        sch.wire_net(n1, [[_P(U, upin), _P(R, lpin)]])
        n2 = "D%s_%d" % (tag, k)
        sch.net(n2, ("R" + tag, rpin), ("DS" + tag, dpin))
        sch.wire_net(n2, [[_P(R, rpin), _P(DS, dpin)]])

    # 第 8 只电阻驱动小数点: R.9 -> DS.5(DP)
    sch.net("DP" + tag, ("R" + tag, "9"), ("DS" + tag, "5"))
    sch.wire_net("DP" + tag, [[_P(R, "9"), _P(DS, "5")]])

    # U.8 与 R.8 各落到自己的 GND 符号 (教材: R 下方一只, U 下方一只)
    sch.net("GND", ("R" + tag, "8"), ("U" + tag, "8"))
    sch.wire_net("GND", [
        [_P(U, "8"), (_X(U, "8"), uy + 130)],
        [_P(R, "8"), (_X(R, "8") - 40, uy + 80), (_X(R, "8") - 40, uy + 130)],
    ])
    sch.port("GND", _X(U, "8"), uy + 130, style=4, orientation=3)
    sch.port("GND", _X(R, "8") - 40, uy + 130, style=4, orientation=3)

    # VCC: 左竖轨接 BI/RBI/LT (U.4/U.5/U.3); U.16 顶部轨 -> DS 公共阳极
    #      竖轨只跨 uy-30..uy+30, 故不会与下方数据横线 (uy+40..uy+70) 相交。
    sch.net("VCC", ("U" + tag, "16"), ("U" + tag, "4"), ("U" + tag, "5"),
            ("U" + tag, "3"), ("DS" + tag, "3"), ("DS" + tag, "8"))
    sch.wire_net("VCC", [
        [(340, uy - 30), (340, uy + 30)],
        [(340, uy + 10), _P(U, "4")],
        [(340, uy + 20), _P(U, "5")],
        [(340, uy + 30), _P(U, "3")],
        [_P(U, "16"), (_X(U, "16"), uy - 40), (1080, uy - 40)],
        [(1080, uy - 40), (1080, uy - 60)],
        [_P(DS, "3"), (1020, _Y(DS, "3")), (1020, uy - 40)],
        [_P(DS, "8"), (1050, _Y(DS, "8")), (1050, uy - 40)],
    ])
    sch.port("VCC", 340, uy - 30, style=2, orientation=1)
    sch.port("VCC", 1080, uy - 60, style=2, orientation=1)
    return U, R, DS


def build_lab2():
    """图4-75 实践题(2): 双路 74LS47 + Res Pack3 + 共阳数码管.

    uy1=310 让 P2 的 8..5 脚与 U1 的 A..D 脚同行 -> 四条水平直线直连;
    P2 的 4..1 脚经 x=320/300/280/260 四条竖管下行到 U2 (uy2=800)。
    竖管最右 320 < 左竖轨 340, 且 U2 的数据横线在 uy+40..70 高于竖轨下端点
    uy+30, 故两处都不相交。
    """
    sch = sch_build.Schematic(1200, 1060, title="图4-75 数码管译码显示")
    DEV_, CON_ = DEV, CON

    # 顶部: P1 电源端子 + C1 去耦 (照教材)
    p1 = sch.place_pin("P1", "Header 2", CON_, "2", 150, 180, rot=180, value="Header 2")
    c1 = sch.place_pin("C1", "Cap", DEV_, "1", 260, 180, value="0.1uF")
    p1.set_text(-50, -16, -50, 34)
    c1.set_text(6, -14, 6, 22)

    # 左: P2 Header 8 -> 两路 4 位数据 (rot180, 引脚 8 在上 / 1 在下)
    p2 = sch.place_pin("P2", "Header 8", CON_, "8", 220, 350, rot=180, value="Header 8")
    p2.set_text(-50, -16, -50, 34)

    U1, R1, DS1 = _channel(sch, "1", 310)
    U2, R2, DS2 = _channel(sch, "2", 800)

    # 顶层电源网表
    sch.net("VCC", ("P1", "2"), ("C1", "1"))
    sch.net("GND", ("P1", "1"), ("C1", "2"))

    # P2 -> U1/U2 数据线: 8,7,6,5 -> U1 的 A,B,C,D (同行直连)
    #                     4,3,2,1 -> U2 的 A,B,C,D (四条竖管下行)
    plan = [("8", U1, "7", 0), ("7", U1, "1", 0), ("6", U1, "2", 0),
            ("5", U1, "6", 0), ("4", U2, "7", 320), ("3", U2, "1", 300),
            ("2", U2, "2", 280), ("1", U2, "6", 260)]
    for ppin, u, upin, vx in plan:
        nm = "DAT_%s_%s" % (u.ref, ppin)
        sch.net(nm, ("P2", ppin), (u.ref, upin))
        a, b = _P(p2, ppin), _P(u, upin)
        if a[1] == b[1]:                       # 同一行 -> 一条水平线
            sch.wire_net(nm, [[a, b]])
        else:
            sch.wire_net(nm, [[a, (vx, a[1]), (vx, b[1]), b]])

    # P1 / C1 电源走线 (照教材: VCC 上抽, GND 下抽)
    sch.wire_net("VCC", [
        [_P(p1, "2"), _P(c1, "1")],
        [(200, 180), (200, 150)],
    ])
    sch.port("VCC", 200, 150, style=2, orientation=1)
    sch.wire_net("GND", [
        [_P(c1, "2"), (290, 240), (240, 240)],
        [_P(p1, "1"), (240, 190), (240, 240), (240, 265)],
    ])
    sch.port("GND", 240, 265, style=4, orientation=3)

    sch.note("图4-75 实践题(2): 双路 74LS47AN + Res Pack3 + 共阳数码管", 60, 1010)
    _quiet(sch, show_desig=(p1, p2))
    for p in (U1, R1, DS1, U2, R2, DS2):
        p.symbol.show_pin_designators = True
    return sch


# ------------------------------------------------------------------ build --
def build(circuit_id, progress=None):
    def _p(step, msg, pct, level="info"):
        if progress:
            progress(level, step, msg, pct)

    out_dir = os.path.join(os.path.dirname(HERE), "out")
    os.makedirs(out_dir, exist_ok=True)

    _p("place", "放置器件 (全部取自 Altium 官方库) ...", 10)
    if circuit_id == "lab1":
        sch = build_lab1()
        title = "AT89C51_图4-74_多谐振荡器"
    elif circuit_id == "lab2":
        sch = build_lab2()
        title = "Chap4-2_图4-75_数码管译码"
    else:
        raise ValueError("unknown circuit %r" % circuit_id)
    libs = sorted({p.lib for p in sch.parts})
    _p("place", "器件放置完成: %d 个, 库: %s" % (len(sch.parts), ", ".join(libs)), 25)

    _p("wire", "照图布线 ...", 35)
    _p("wire", "网络: %s" % ", ".join(sorted(sch.nets.keys())), 50)

    _p("erc", "ERC 电气规则检查 ...", 60)
    issues = erc.check(sch)
    counts = erc.summarize(issues)
    _p("erc", "ERC 完成: 错误 %d / 警告 %d / 信息 %d" %
       (counts["ERROR"], counts["WARN"], counts["INFO"]), 70)

    _p("save", "写入原生 .SchDoc ...", 80)
    doc_path = os.path.join(out_dir, title + ".SchDoc")
    sch.save(doc_path)
    _p("save", "已写出 %s (%d 字节)" % (os.path.basename(doc_path), os.path.getsize(doc_path)), 90)

    svg_path = os.path.join(out_dir, title + ".svg")
    render_svg(sch, svg_path, title)
    _p("save", "SVG 预览已生成", 95)

    return {
        "id": circuit_id,
        "title": title,
        "doc": doc_path,
        "svg": svg_path,
        "parts": len(sch.parts),
        "nets": len(sch.nets),
        "erc": counts,
        "issues": [str(i) for i in issues if i.level == "ERROR"],
    }


# ------------------------------------------------------------- svg preview --
def _num(props, key, default=0):
    try:
        return int(props.get(key, default))
    except (TypeError, ValueError):
        return default


def _symbol_svg(pts, part):
    """Draw the symbol's own graphics from the (transformed) raw records."""
    for _props, raw in part.symbol.children:
        props = {k.upper(): v for k, v in sch_build.split_props(raw)}
        rec = props.get("RECORD")
        if rec == "14":
            x0, y0 = part.x + _num(props, "LOCATION.X"), part.y + _num(props, "LOCATION.Y")
            x1, y1 = part.x + _num(props, "CORNER.X"), part.y + _num(props, "CORNER.Y")
            pts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#fff" '
                       'stroke="#333" stroke-width="1.2"/>' %
                       (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)))
        elif rec == "13":
            pts.append('<path d="M%d,%d L%d,%d" fill="none" stroke="#333" '
                       'stroke-width="1.2"/>' %
                       (part.x + _num(props, "LOCATION.X"), part.y + _num(props, "LOCATION.Y"),
                        part.x + _num(props, "CORNER.X"), part.y + _num(props, "CORNER.Y")))
        elif rec in ("6", "7"):
            n = _num(props, "LOCATIONCOUNT")
            p = [(part.x + _num(props, "X%d" % i), part.y + _num(props, "Y%d" % i))
                 for i in range(1, n + 1)]
            if len(p) >= 2:
                d = "M" + " L".join("%d,%d" % q for q in p)
                fill = ' fill="#c8dce8"' if rec == "7" else ' fill="none"'
                pts.append('<path d="%s"%s stroke="#333" stroke-width="1.2"/>' % (d, fill))
        elif rec == "8":
            pts.append('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="#333" '
                       'stroke-width="1.2"/>' %
                       (part.x + _num(props, "LOCATION.X"), part.y + _num(props, "LOCATION.Y"),
                        _num(props, "RADIUS", 5)))
        elif rec == "4":
            txt = props.get("TEXT", "")
            if txt:
                pts.append('<text x="%d" y="%d" font-size="9" fill="#333">%s</text>'
                           % (part.x + _num(props, "LOCATION.X"),
                              part.y + _num(props, "LOCATION.Y"), txt))


def render_svg(sch, path, title):
    """SVG preview mirroring sch_build's emission."""
    W, H = sch.width, sch.height
    pts = []
    for part in sch.parts:
        minx, miny, _mx, _my = part.bounds()
        pts.append('<text x="%d" y="%d" font-size="12" fill="#185fa5" '
                   'font-family="monospace">%s</text>'
                   % (part.x + minx, part.y + miny - 3, part.ref))
        _symbol_svg(pts, part)
    for name, entry in sch.plan_nets().items():
        color = "#c0392b" if sch.is_power(name) else "#2c3e50"
        for poly in entry["wires"]:
            if len(poly) >= 2:
                d = "M" + " L".join("%d,%d" % p for p in poly)
                pts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3"/>' % (d, color))
        for nm, x, y in entry["labels"]:
            pts.append('<text x="%d" y="%d" font-size="10" fill="#7f8c8d">%s</text>'
                       % (x, y - 3, nm))
        for nm, x, y, _orient, _style in entry["ports"]:
            pts.append('<circle cx="%d" cy="%d" r="7" fill="none" stroke="%s" '
                       'stroke-width="1.3"/>' % (x, y, color))
            pts.append('<text x="%d" y="%d" font-size="10" fill="%s">%s</text>'
                       % (x + 9, y + 3, color, nm))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'font-family="monospace">' % (W, H))
    svg += '<rect x="0" y="0" width="%d" height="%d" fill="#fafafa"/>' % (W, H)
    svg += "".join(pts)
    svg += '<text x="20" y="%d" font-size="14" fill="#333">%s</text>' % (H - 10, title)
    svg += '</svg>'
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)


if __name__ == "__main__":
    import json

    cid = sys.argv[1] if len(sys.argv) > 1 else "all"
    todo = ["lab1", "lab2"] if cid == "all" else [cid]
    for name in todo:
        print("=" * 60)
        print("构建 %s" % name)
        print("=" * 60)
        res = build(name, progress=lambda lv, st, m, p: print("[%s] %s (%d%%) %s"
                                                              % (lv, st, p, m)))
        print(json.dumps({k: v for k, v in res.items() if k != "issues"},
                         ensure_ascii=False, indent=2))
        if res["issues"]:
            print("ERRORS:")
            for i in res["issues"]:
                print("  ", i)
