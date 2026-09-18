# -*- coding: utf-8 -*-
"""生成 Altium `.PrjPCB` 工程文件。

用法:
    python tools/make_project.py MyProject.PrjPCB Top_Level.SchDoc S1.SchDoc S2.SchDoc

注意两个坑（详见 docs/prjpcb-format.md）:
  * 顶层段名必须是 [Design]，写成 [Design_Project] 会被加载但成员全部丢失
  * 中文路径按 GBK 编码写入
"""
import sys

DESIGN_HEAD = [
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

DOCUMENT_TAIL = [
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
    "",
]

CONFIG = [
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


def build(names):
    body = list(DESIGN_HEAD)
    for i, n in enumerate(names, 1):
        body += ["", "[Document%d]" % i, "DocumentPath=%s" % n] + DOCUMENT_TAIL
    body += CONFIG
    return "\r\n".join(body)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    out = sys.argv[1]
    docs = sys.argv[2:]
    text = build(docs)
    try:
        raw = text.encode("gbk")
    except UnicodeEncodeError:
        raw = text.encode("utf-8-sig")
    with open(out, "wb") as f:
        f.write(raw)
    print("已生成 %s (%d 字节, %d 个成员)" % (out, len(raw), len(docs)))
    for d in docs:
        print("  -", d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
