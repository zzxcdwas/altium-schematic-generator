# -*- coding: utf-8 -*-
"""用 Win32 SHFileOperationW(FO_DELETE|FOF_ALLOWUNDO) 把目录送进回收站。"""
import ctypes
import os
import sys
from ctypes import wintypes

FO_DELETE = 3
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_NOERRORUI = 0x0400
FOF_SILENT = 0x0004


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def to_recycle_bin(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False, "路径不存在"
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0"          # 双 null 结尾
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    aborted = bool(op.fAnyOperationsAborted)
    return (rc == 0 and not aborted), "rc=%d aborted=%s" % (rc, aborted)


if __name__ == "__main__":
    target = sys.argv[1]
    ok, msg = to_recycle_bin(target)
    print("target :", target)
    print("result :", "OK 已送入回收站" if ok else "FAIL " + msg)
    print("exists :", os.path.exists(target))
