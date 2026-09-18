# -*- coding: utf-8 -*-
"""最小上手示例：两个电容并联接 GND，用 AD 自带库画出来。

运行:
    python examples/01_minimal_schematic.py

产出:
    out/01_minimal.SchDoc   —— 可直接用 Altium Designer 打开
    out/01_minimal.svg      —— 矢量预览

要点:
  * 所有元器件都取自 Altium 官方库，没有一条自绘线条；
  * place_pin() 直接把某个引脚的「电气热点」钉在给定坐标上，
    不需要手算每个元件符号原点的偏移量；
  * net() 声明网络成员，wire_net() 画显式导线，
    save() 时自动生成导线、结点、电源端口。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import sch_build

# AD 自带库，任何装了 Altium 的机器上都有
DEV = "Miscellaneous Devices.IntLib"


def main():
    sch = sch_build.Schematic(width=300, height=220, title="01_minimal")

    # 把 C1 的 1 号引脚热点钉在 (100, 60)，2 号脚自然落在 (100, 85)
    sch.place_pin("C1", "Cap", DEV, "1", 100, 60)
    # C2 与 C1 并排
    sch.place_pin("C2", "Cap", DEV, "1", 180, 60)

    # 两个网络
    sch.net("IN", ("C1", "1"), ("C2", "1"))
    sch.net("GND", ("C1", "2"), ("C2", "2"))

    # 显式布线：横线把两脚连起来，竖线拉到下方 GND 主干
    sch.wire_net("IN", [[(100, 60), (180, 60)]])
    sch.wire_net("GND", [
        [(100, 85), (100, 140)],
        [(180, 85), (180, 140)],
        [(100, 140), (180, 140)],
    ])
    sch.power_port("GND", 140, 140)

    out = os.path.join(ROOT, "out", "01_minimal.SchDoc")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sch.save(out)

    svg = os.path.join(ROOT, "out", "01_minimal.svg")
    open(svg, "w", encoding="utf-8").write(sch.render())
    print("已生成:")
    print("  %s (%d 字节)" % (out, os.path.getsize(out)))
    print("  %s" % svg)


if __name__ == "__main__":
    main()
