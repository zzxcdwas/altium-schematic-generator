# -*- coding: utf-8 -*-
"""集中管理与本机相关的可配置项。

开源出去的代码里不应该写死任何一台机器的路径，所有本机相关的值都通过
环境变量注入，找不到时再退到「常见安装位置自动探测」。

环境变量:
    ALT_LIB_ROOT   Altium 原理图库目录 (含 *.SchLib / *.IntLib)
                   默认自动探测常见安装位置的 Documents\\Library
    ALT_AD_EXE     DXP.EXE 完整路径，仅 ad_open / 截图辅助脚本用到
"""

import os
import glob

# Altium 常见安装根目录（依次为官方默认、D 盘、E 盘、C 盘 Program Files）
_AD_HINTS = [
    r"C:\Program Files\Altium\*",
    r"C:\Program Files (x86)\Altium\*",
    r"D:\SoftWare\AD*",
    r"E:\SoftWare\AD*",
    r"C:\SoftWare\AD*",
    r"D:\Altium\*",
]

# 单个 .SchLib 文件的候选目录（相对 Altium 安装根）
_LIB_SUBDIRS = [
    os.path.join("Documents", "Library"),
    "Library",
    os.path.join("Documents", "Altium", "Library"),
]


def ad_install_root():
    """返回 Altium 安装根目录，找不到返回 None。"""
    env = os.environ.get("ALT_AD_ROOT")
    if env and os.path.isdir(env):
        return env
    for hint in _AD_HINTS:
        for cand in sorted(glob.glob(hint), reverse=True):
            for sub in _LIB_SUBDIRS:
                if os.path.isdir(os.path.join(cand, sub)):
                    return cand
    return None


def lib_root():
    """返回原理图库目录。

    优先 ALT_LIB_ROOT；否则在探测到的安装根目录下找 Library 子目录。
    """
    env = os.environ.get("ALT_LIB_ROOT")
    if env:
        return env
    root = ad_install_root()
    if root:
        for sub in _LIB_SUBDIRS:
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                return p
    # 最后手段：当前目录（便于把库文件和脚本放一起）
    return os.getcwd()


def ad_exe():
    """返回 DXP.EXE 路径（AD16 时代的可执行文件名）。"""
    env = os.environ.get("ALT_AD_EXE")
    if env and os.path.exists(env):
        return env
    root = ad_install_root()
    if root:
        for cand in ("DXP.EXE", os.path.join("System", "DXP.EXE")):
            p = os.path.join(root, cand)
            if os.path.exists(p):
                return p
    return None


def describe():
    """打印当前解析到的配置，便于排查环境问题。"""
    return {
        "ALT_LIB_ROOT": lib_root(),
        "ALT_AD_ROOT": ad_install_root(),
        "ALT_AD_EXE": ad_exe(),
    }


if __name__ == "__main__":
    for k, v in describe().items():
        print("%-14s = %s" % (k, v))
