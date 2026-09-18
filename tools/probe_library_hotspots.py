# -*- coding: utf-8 -*-
"""探测任意官方库元件在各旋转角下的引脚热点（相对 place_pin 锚点）。

这是能自己扩展库件支持的必备工具：换一个新元件时先跑它，
拿到准确热点再做布局，不要凭肉眼猜。

用法:
    python tools/probe_library_hotspots.py "Miscellaneous Devices.IntLib" Cap Inductor
    python tools/probe_library_hotspots.py "01-电阻-电容-电感.SchLib" RES CAP --rot 0 90 270

输出坐标系: 以 place_pin() 锚定的那个引脚为原点 (0,0) —— 即实际布局时
            其他引脚相对锚点的偏移量。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import sch_build  # noqa: E402

# 方向码 -> 单位向量 * 引脚长度(库空间)
_VEC = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}


def hotspots(symbol):
    """返回 [( designator, 热点x, 热点y )]，坐标已翻转到设计空间。"""
    out = []
    for p in symbol.pins:
        dx, dy = _VEC[p["direction"]]
        L = p["length"]
        out.append((str(p["designator"]),
                    p["x"] + dx * L,
                    p["y"] + dy * L))

    # 固定以编号最小的引脚为基准，输出才稳定可复现
    def _key(item):
        d = item[0]
        return (0, int(d), "") if d.isdigit() else (1, 0, d)

    if any(d.isdigit() for d, _, _ in out):
        out.sort(key=_key)
    return out


def probe(libname, comp, rots):
    try:
        syms = sch_build.load_lib(libname)
    except Exception as e:
        print("  [ERROR] 加载库失败: %s" % e)
        return
    if comp not in syms:
        print("  [ERROR] 库里没有元件 %r" % comp)
        return
    print("\n%s  /  %s" % (libname, comp))
    for rot in rots:
        sym = syms[comp].transformed(rot, False)
        hs = hotspots(sym)
        if not hs:
            continue
        # 归一化：以 1 号脚(或第一个脚)为原点
        base = hs[0]
        rel = [(d, x - base[1], y - base[2]) for d, x, y in hs]
        print("  rot=%-4d " % rot + "  ".join(
            "pin%s=(%d,%d)" % (d, x, y) for d, x, y in rel))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lib", help="库文件名, 如 'Miscellaneous Devices.IntLib'")
    ap.add_argument("components", nargs="+", help="元件名, 可多个")
    ap.add_argument("--rot", nargs="+", type=int, default=[0, 90, 180, 270],
                    help="要探测的旋转角, 默认 0 90 180 270")
    args = ap.parse_args()
    print("库目录: %s" % sch_build.LIBROOT)
    for comp in args.components:
        probe(args.lib, comp, args.rot)


if __name__ == "__main__":
    main()
