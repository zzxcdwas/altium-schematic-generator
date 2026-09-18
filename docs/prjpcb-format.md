# `.PrjPCB` 工程文件格式

层次化原理图**必须**放在工程里才能正确编译。`.PrjPCB` 是纯文本 INI 风格文件。

## 最小可用模板

```
[Design]
Version=1.0
HierarchyMode=0
ChannelRoomNamingStyle=0
ReleasesFolder=
ReleaseVaultGUID=
ReleaseVaultName=
ChannelDesignatorFormatString=$Component_$RoomName
ChannelRoomLevelSeperator=_
OpenOutputs=1
ArchiveProject=0
TimestampOutput=0
SeparateFolders=0
TemplateLocationPath=
PinSwapBy_Netlabel=1
PinSwapBy_Pin=1
AllowPortNetNames=0
AllowSheetEntryNetNames=1
AppendSheetNumberToLocalNets=0
NetlistSinglePinNets=0
DefaultConfiguration=Default Configuration
UserID=0xFFFFFFFF
DefaultPcbProtel=1
DefaultPcbPcad=0
ReorderDocumentsOnCompile=1
NameNetsHierarchically=0
PowerPortNamesTakePriority=0
PushECOToAnnotationFile=1
DItemRevisionGUID=
ReportSuppressedErrorsInMessages=0
OutputPath=
LogFolderPath=
ManagedProjectGUID=

[Preferences]
PrefsVaultGUID=
PrefsRevisionGUID=

[Document1]
DocumentPath=Top_Level.SchDoc
AnnotationEnabled=1
AnnotateStartValue=1
AnnotationIndexControlEnabled=0
AnnotateSuffix=
AnnotateScope=All
AnnotateOrder=-1
DoLibraryUpdate=1
DoDatabaseUpdate=1
ClassGenCCAutoEnabled=1
ClassGenCCAutoRoomEnabled=1
ClassGenNCAutoScope=None
DItemRevisionGUID=
GenerateClassCluster=0
DocumentUniqueId=

[Document2]
DocumentPath=S1.SchDoc
...

[Configuration1]
Name=Default Configuration
ParameterCount=0
ConstraintFileCount=0
ReleaseItemId=
CurrentRevision=
Variant=[No Variations]
GenerateBOM=1
OutputJobsCount=0
```

## 铁律

1. **顶层段名必须是 `[Design]`**。写成 `[Design_Project]` 时，AD 能加载文件，
   但 Projects 面板会显示 `no documents` —— 成员一个都不认。
2. **每个文档单独一个 `[DocumentN]` 段**，序号从 1 递增。
3. `DocumentPath` 写**相对路径**（相对于工程文件所在目录）。
4. 中文文件名/路径按 **GBK** 编码写入。
5. 换行用 `\r\n`。
6. `[Configuration1]` 段不能缺，否则打开时提示工程损坏。

## 自动化

用 `tools/make_project.py` 生成，避免手写出错：

```bash
python tools/make_project.py MyProject.PrjPCB Top_Level.SchDoc S1.SchDoc S2.SchDoc
```
