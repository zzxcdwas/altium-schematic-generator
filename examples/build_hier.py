# -*- coding: utf-8 -*-
"""教材 图7-12「层次化电路图连接关系」1:1 复原生成器 (v1)。

四份文档, 全部元器件取自 AD16 官方库:
  Oscillator.SchDoc  完整振荡器 (左图: S1+S2 合并的原始电路)
  S1.SchDoc          振荡器驱动半边: VCC/L1/R1/Q1/R2/R3/C5, C1->P1, C2->P2
  S2.SchDoc          选频槽路半边: P3->L2/C3, C4->P4, 槽路中点接地
  Top_Level.SchDoc   顶层: 两个图纸符号, Sheet Entry P1<->P3, P2<->P4 连线

库件 (与 v14 同源, 热点均经 AD16 实测):
  RES      01-电阻-电容-电感.SchLib   rot270 竖放: pin1(0,0) pin2(0,40)
  CAP      01-电阻-电容-电感.SchLib   rot0 竖放: pin1(0,0) pin2(0,25)
                                      rot90 横放: pin1(0,0) pin2(25,0)
  Inductor Miscellaneous Devices.IntLib rot270 竖放: pin1(0,0) pin2(0,60)
  9013-DIP 04-三极管.SchLib           rot0: C(0,0) B(-20,20) E(0,40)

层次化对象 (RECORD=15/16/18) 的字段与几何语义逐一对照 AD16 自带样例
(Bluetooth Sentinel/Bluetooth_Sentinel.SchDoc, Host_Controller.SchDoc):
  - 图纸符号 LOCATION = 设计空间左上角, 向下延伸 YSIZE;
  - 入口 SIDE 0=左 1=右 2=上 3=下, DISTANCEFROMTOP 以 10 为单位从顶边下移;
  - 端口 LOCATION = 本体左端, 向右延伸 WIDTH, 两端皆连接点。
"""
import os
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)              # 示例自身
sys.path.insert(0, os.path.join(ROOT, "src"))   # 核心库

import erc
import sch_build

OUT = os.path.join(ROOT, "out")

RES_LIB = "01-电阻-电容-电感.SchLib"
MD_LIB = "Miscellaneous Devices.IntLib"
NPN_LIB = "04-三极管.SchLib"


# --------------------------------------------------------------------------
# 通用子电路: 振荡器驱动半边 (S1 的全部内容; Oscillator 复用同一布局)
# --------------------------------------------------------------------------

def add_drive_section(sch, with_ports):
    """VCC/L1/R1/Q1/R2/R3/C5 + C1(->N_TOP 或 P1) + C2(->N_FB 或 P2)。

    with_ports=True  -> C1.2 接端口 P1、C2.1 接端口 P2 (S1.SchDoc)
    with_ports=False -> C1.2 接网 N_TOP、C2.1 接网 N_FB (Oscillator.SchDoc)
    返回关键热点坐标供上层继续布线。
    """
    # 摆件 (锚点=引脚热点)
    sch.place_pin("L1", "Inductor", MD_LIB, "1", 220, 60, rot=270)   # pin2=(220,120)
    sch.place_pin("R1", "RES", RES_LIB, "1", 140, 60, rot=270)       # pin2=(140,100)
    sch.place_pin("R2", "RES", RES_LIB, "1", 140, 240, rot=270)      # pin2=(140,280)
    sch.place_pin("R3", "RES", RES_LIB, "1", 220, 240, rot=270)      # pin2=(220,280)
    sch.place_pin("Q1", "9013-DIP", NPN_LIB, "3", 220, 140, rot=0)   # B(200,160) E(220,180)
    sch.place_pin("C1", "CAP", RES_LIB, "1", 260, 140, rot=90)       # pin2=(285,140)
    sch.place_pin("C2", "CAP", RES_LIB, "1", 80, 160, rot=90)        # pin2=(105,160)
    sch.place_pin("C5", "CAP", RES_LIB, "1", 270, 220, rot=90)       # pin2=(295,220)

    # VCC: 顶轨
    sch.net("VCC", ("L1", "1"), ("R1", "1"))
    sch.wire_net("VCC", [[(140, 60), (220, 60)]])
    sch.port("VCC", 220, 60, style=2, orientation=1)

    # 集电极: L1.2 - Q1.C - C1.1 (T 结点, 教材有 dot)
    sch.net("N_COLL", ("L1", "2"), ("Q1", "3"), ("C1", "1"))
    sch.wire_net("N_COLL", [[(220, 120), (220, 140)], [(220, 140), (260, 140)]])
    sch.hier_junction(220, 140)

    # 基极: R1.2/R2.1/C2.2/Q1.B (十字结点, 教材有 dot)
    sch.net("N_BASE", ("R1", "2"), ("R2", "1"), ("C2", "2"), ("Q1", "2"))
    sch.wire_net("N_BASE", [[(140, 100), (140, 240)], [(105, 160), (200, 160)]])

    # 发射极: Q1.E - R3.1 - C5.1 (T 结点)
    sch.net("N_EMIT", ("Q1", "1"), ("R3", "1"), ("C5", "1"))
    sch.wire_net("N_EMIT", [[(220, 180), (220, 240)], [(220, 220), (270, 220)]])

    # 地: R2.2/R3.2/C5.2 -> 底部横轨 -> GND
    sch.net("GND", ("R2", "2"), ("R3", "2"), ("C5", "2"))
    sch.wire_net("GND", [
        [(140, 280), (140, 330)],
        [(220, 280), (220, 330)],
        [(295, 220), (295, 330)],
        [(140, 330), (295, 330)],
        [(220, 330), (220, 350)],
    ])
    sch.port("GND", 220, 350, style=4, orientation=3)

    if with_ports:
        # C1.2 -> 端口 P1 ; C2.1 -> 反馈环 -> 端口 P2
        sch.net("P1", ("C1", "2"))
        sch.wire_net("P1", [[(285, 140), (315, 140)]])
        sch.hier_port("P1", 315, 140)

        sch.net("P2", ("C2", "1"))
        sch.wire_net("P2", [[(80, 160), (40, 160)], [(40, 160), (40, 400)],
                            [(40, 400), (405, 400)]])
        sch.hier_port("P2", 405, 400)
        top_net, bot_net = "P1", "P2"
    else:
        top_net, bot_net = "N_TOP", "N_FB"
    return {"c1_right": (285, 140), "c2_left": (80, 160), "top_net": top_net,
            "bot_net": bot_net}


def add_tank_section(sch, x0, y0, top_net, bot_net):
    """选频槽路: <top_net> -> L2/C3 ; C4 -> <bot_net> ; 槽路中点接地。

    (x0, y0) = C3.pin1 (槽路立柱顶端下方 10 格), L2 在 x0+70。
    """
    c3 = (x0, y0)                    # C3.1
    c3b = (x0, y0 + 25)              # C3.2
    c4 = (x0, y0 + 45)               # C4.1
    c4b = (x0, y0 + 70)              # C4.2
    l2t = (x0 + 70, y0 - 10)         # L2.1
    l2b = (x0 + 70, y0 + 50)         # L2.2
    bot = (x0, y0 + 100)             # 底部角
    sch.place_pin("C3", "CAP", RES_LIB, "1", c3[0], c3[1], rot=0)
    sch.place_pin("C4", "CAP", RES_LIB, "1", c4[0], c4[1], rot=0)
    sch.place_pin("L2", "Inductor", MD_LIB, "1", l2t[0], l2t[1], rot=270)

    # 顶: <top_net> -> 节点A(dot) -> C3.1 / L2.1
    sch.net(top_net, ("C3", "1"), ("L2", "1"))
    sch.wire_net(top_net, [
        [(c3[0], c3[1] - 70), (c3[0], c3[1])],        # 从上方引入
        [(c3[0], y0 - 10), (l2t[0], l2t[1])],         # 分支到 L2 顶
    ])

    # 中点: C3.2 - C4.1, 中点接地 (教材 GND 在槽路左侧)
    sch.net("GND", ("C3", "2"), ("C4", "1"))
    sch.wire_net("GND", [
        [(c3b[0], c3b[1]), (c4[0], c4[1])],
        [(c3b[0], c3b[1] + 10), (x0 - 70, y0 + 35)],
        [(x0 - 70, y0 + 35), (x0 - 70, y0 + 55)],
    ])
    sch.port("GND", x0 - 70, y0 + 55, style=4, orientation=3)

    # 底: C4.2 - 节点C(dot) - L2.2, 并引向 <bot_net>
    sch.net(bot_net, ("C4", "2"), ("L2", "2"))
    sch.wire_net(bot_net, [
        [(c4b[0], c4b[1]), (c4b[0], bot[1])],
        [(c4b[0], bot[1]), (l2b[0], bot[1])],
        [(l2b[0], l2b[1]), (l2b[0], bot[1])],
    ])
    return {"c4_bottom": c4b, "bot_corner": (x0, bot[1]), "l2_bottom": l2b,
            "bot_y": bot[1]}


# --------------------------------------------------------------------------
# 四份文档
# --------------------------------------------------------------------------

def build_s1():
    sch = sch_build.Schematic(width=460, height=470, title="S1")
    add_drive_section(sch, with_ports=True)
    return sch


def build_s2():
    sch = sch_build.Schematic(width=400, height=380, title="S2")
    add_tank_section(sch, 220, 210, "P3", "P4")
    # P3/P4 端口与引入线 (端口本体右端 = LOCATION+WIDTH)
    sch.hier_port("P3", 120, 140)
    sch.wire_net("P3", [[(150, 140), (220, 140)]])
    sch.hier_port("P4", 120, 310)
    sch.wire_net("P4", [[(150, 310), (220, 310)]])
    return sch


def build_top():
    sch = sch_build.Schematic(width=520, height=260, title="Top_Level")
    # 图纸符号: (x, y_top, w, h, 名称, 子图文件, [(入口名, 边, 自顶距离)])
    sch.hier_symbol(80, 80, 180, 90, "S1", "S1.SchDoc",
                    [("P1", 1, 2), ("P2", 1, 4)])
    sch.hier_symbol(340, 80, 140, 90, "S2", "S2.SchDoc",
                    [("P3", 0, 2), ("P4", 0, 4)])
    # 入口互联: S1 右侧 P1/P2  ->  S2 左侧 P3/P4
    sch.hier_wire("LINK_TOP", [[(260, 100), (340, 100)]])
    sch.hier_wire("LINK_BOT", [[(260, 120), (340, 120)]])
    return sch


def build_oscillator():
    sch = sch_build.Schematic(width=760, height=480, title="Oscillator")
    sec = add_drive_section(sch, with_ports=False)
    tank = add_tank_section(sch, 560, 210, "N_TOP", "N_FB")

    # C1.2 -> 槽路顶节点
    sch.net("N_TOP", ("C1", "2"))
    sch.wire_net("N_TOP", [[(sec["c1_right"][0], sec["c1_right"][1]),
                            (560, 140)]])

    # 槽路底 -> C2 反馈环 (经左、底、右三边回到 C2.1)
    sch.net("N_FB", ("C2", "1"))
    sch.wire_net("N_FB", [
        [(sec["c2_left"][0], sec["c2_left"][1]), (40, 160)],
        [(40, 160), (40, 430)],
        [(40, 430), (630, 430)],
        [(630, 430), (tank["l2_bottom"][0], tank["bot_corner"][1])],
    ])
    return sch


BUILDERS = [
    ("Oscillator.SchDoc", build_oscillator),
    ("S1.SchDoc", build_s1),
    ("S2.SchDoc", build_s2),
    ("Top_Level.SchDoc", build_top),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    report = []
    ok = True
    for name, fn in BUILDERS:
        sch = fn()
        issues = erc.check(sch)
        n_err = sum(1 for i in issues if i.level == "ERROR")
        n_warn = sum(1 for i in issues if i.level == "WARN")
        path = sch.save(os.path.join(OUT, name))
        report.append("### %s" % name)
        report.append("  器件 %d / 网络 %d / ERC 错误 %d 警告 %d 信息 %d"
                      % (len(sch.parts), len(sch.nets), n_err, n_warn,
                         sum(1 for i in issues if i.level == "INFO")))
        for i in issues:
            report.append("    %s" % i)
        if n_err:
            ok = False
        report.append("  保存: %r" % (path,))
        report.append("")
    text = "\n".join(report)
    print(text)
    open(os.path.join(OUT, "_hier_build.txt"), "w", encoding="utf-8").write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
