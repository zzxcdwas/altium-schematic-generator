# -*- coding: utf-8 -*-
"""把最终原理图产物整理到用户的 AD16 文件夹，并生成 .PrjPCB 工程。"""
import os
import shutil
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

# 交付目录：命令行参数 > 环境变量 > 当前目录下的 deliver/
DST = os.environ.get("ALT_DEPLOY_DIR") or os.path.join(os.getcwd(), "deliver")

# (源文件名, 目标文件名)
FILES = [
    ("AT89C51_图4-74_多谐振荡器.SchDoc", "图4-74_多谐振荡器.SchDoc"),
    ("Chap4-2_图4-75_数码管译码.SchDoc", "图4-75_数码管译码.SchDoc"),
    ("Top_Level.SchDoc", "Top_Level.SchDoc"),
    ("Oscillator.SchDoc", "Oscillator.SchDoc"),
    ("S1.SchDoc", "S1.SchDoc"),
    ("S2.SchDoc", "S2.SchDoc"),
]

# (工程文件名, [成员 SchDoc])
PROJECTS = [
    ("图4-74_多谐振荡器.PrjPCB", ["图4-74_多谐振荡器.SchDoc"]),
    ("图4-75_数码管译码.PrjPCB", ["图4-75_数码管译码.SchDoc"]),
    ("图7-12_层次化.PrjPCB",
     ["Top_Level.SchDoc", "Oscillator.SchDoc", "S1.SchDoc", "S2.SchDoc"]),
]

# 附带的可视化对照页（可选，文件不存在就跳过）
EXTRA = [("教材实践题对照_v14.html", "教材实践题对照_v14.html")]


def main():
    os.makedirs(DST, exist_ok=True)
    print("目标目录:", DST)

    for src, dst in FILES + EXTRA:
        s = os.path.join(SRC, src)
        if not os.path.exists(s):
            print("  跳过(不存在):", src)
            continue
        d = os.path.join(DST, dst)
        shutil.copy2(s, d)
        print("  复制 %-34s -> %s (%d B)" % (src, dst, os.path.getsize(d)))

    for pname, docs in PROJECTS:
        p = os.path.join(DST, pname)
        body = [
            "[Design]",
            "Version=1.0",
            "HierarchyMode=0",
            "ChannelRoomNamingStyle=0",
            "ReleasesFolder=",
            "ReleaseVaultGUID=",
            "ReleaseVaultName=",
            "ChannelDesignatorFormatString=$Component_$RoomName",
            "ChannelRoomLevelSeperator=_",
            "OpenOutputs=1",
            "ArchiveProject=0",
            "TimestampOutput=0",
            "SeparateFolders=0",
            "TemplateLocationPath=",
            "PinSwapBy_Netlabel=1",
            "PinSwapBy_Pin=1",
            "AllowPortNetNames=0",
            "AllowSheetEntryNetNames=1",
            "AppendSheetNumberToLocalNets=0",
            "NetlistSinglePinNets=0",
            "DefaultConfiguration=Default Configuration",
            "UserID=0xFFFFFFFF",
            "DefaultPcbProtel=1",
            "DefaultPcbPcad=0",
            "ReorderDocumentsOnCompile=1",
            "NameNetsHierarchically=0",
            "PowerPortNamesTakePriority=0",
            "PushECOToAnnotationFile=1",
            "DItemRevisionGUID=",
            "ReportSuppressedErrorsInMessages=0",
            "OutputPath=",
            "LogFolderPath=",
            "ManagedProjectGUID=",
            "",
            "[Preferences]",
            "PrefsVaultGUID=",
            "PrefsRevisionGUID=",
        ]
        for i, d in enumerate(docs, 1):
            body += [
                "",
                "[Document%d]" % i,
                "DocumentPath=%s" % d,
                "AnnotationEnabled=1",
                "AnnotateStartValue=1",
                "AnnotationIndexControlEnabled=0",
                "AnnotateSuffix=",
                "AnnotateScope=All",
                "AnnotateOrder=-1",
                "DoLibraryUpdate=1",
                "DoDatabaseUpdate=1",
                "ClassGenCCAutoEnabled=1",
                "ClassGenCCAutoRoomEnabled=1",
                "ClassGenNCAutoScope=None",
                "DItemRevisionGUID=",
                "GenerateClassCluster=0",
                "DocumentUniqueId=",
            ]
        body += [
            "",
            "[Configuration1]",
            "Name=Default Configuration",
            "ParameterCount=0",
            "ConstraintFileCount=0",
            "ReleaseItemId=",
            "CurrentRevision=",
            "Variant=[No Variations]",
            "GenerateBOM=1",
            "OutputJobsCount=0",
            "",
        ]
        text = "\r\n".join(body)
        # AD16 工程文件按系统 ANSI(GBK) 写入，中文路径才不会乱码
        try:
            raw = text.encode("gbk")
        except UnicodeEncodeError:
            raw = text.encode("utf-8-sig")
        with open(p, "wb") as f:
            f.write(raw)
        print("  工程 %-30s 成员=%d" % (pname, len(docs)))

    print("\n--- AD16 目录内容 ---")
    for n in sorted(os.listdir(DST)):
        fp = os.path.join(DST, n)
        print("  %-34s %8d B" % (n, os.path.getsize(fp)))


if __name__ == "__main__":
    sys.exit(main())
