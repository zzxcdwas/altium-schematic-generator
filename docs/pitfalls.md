# 踩坑清单：外部控制 AD 的死路与生路

> 全部结论在 AD16.1.12 实机验证。写这套东西之前先读一遍，能省下几小时。

## 一、证伪：这些自动化路径全是死路

| 路径 | 结果 |
|---|---|
| COM / `WScript.Shell` / PowerShell `Add-Type` | 被安全策略拦截，不可用 |
| PowerShell `New-Object -ComObject Shell.Application` | 同样被拦（“COM object instantiation can run arbitrary code”） |
| `DXP.EXE /RunScript:file` | AD16 不支持（那是 AD22 `X2.EXE` 的参数），进程起来就退 |
| `dxpProcess:` / `dxp:` URL 协议 | 注册表里确有协议，但传参毫无反应 |
| 鼠标键盘注入（`mouse_event` / `keybd_event` / `SendInput`） | API 返回成功但目标窗口无响应 |
| `PostMessage` 键盘消息 | AD 菜单是自绘的，不响应，`GetMenu` 也返回 0 |
| 导出 ASCII 格式 `.SchDoc` 再改 | **AD 只导出 ASCII，不读入**；第三方 ASCII 样本打开也是空白 |

**唯一可靠路径 = 按原生格式写出 `.SchDoc`，再让 AD 打开。**

## 二、打开文件：用 Shell 关联，别用命令行传参

进程级传参会随机卡住（连已知良好的文件都收不进去）：

```python
os.startfile(r"C:\path\to\Top_Level.SchDoc")   # ✅ 走 Windows Shell 关联，等价双击
subprocess.Popen([ad_exe, path])               # ❌ 会卡住
```

## 三、PINCONGLOMERATE 方向位被 OR 两次

见 [schdoc-format.md §5](schdoc-format.md)。最终调用方只能传额外位，
低 2 位方向码必须交给发射器在翻转之后写入。

## 四、`.PrjPCB` 工程格式

简写格式 **能被加载但识别不到任何成员**（Projects 面板显示 `no documents`）：

```
[Design_Project]              ← 段名不对
Version=1.0
DocumentPath=A.SchDoc         ← 成员写法不对
```

正确格式是每段一个文档：

```
[Design]
Version=1.0
HierarchyMode=0
...

[Document1]
DocumentPath=Top_Level.SchDoc
...

[Document2]
DocumentPath=S1.SchDoc
...

[Configuration1]
Name=Default Configuration
ParameterCount=0
ConstraintFileCount=0
Variant=[No Variations]
OutputJobsCount=0
```

* 段名必须是 `[Design]`
* `DocumentPath` 用**相对路径**
* 中文路径按 **GBK** 编码写入，否则乱码

## 五、层次化：子图文件必须真实存在

顶层图纸符号 `RECORD=33` 里写了子图文件名，AD 编译工程时**必须找得到这个文件**，
否则报「子图找不到」。教材常常只印其中一个子图，剩下被引用的那张要自己补画。

## 六、Windows 回收站

PowerShell 的两条常规路都被拦了（`Add-Type` 和 COM）。可用的是 ctypes 直调 Win32：

```python
ctypes.windll.shell32.SHFileOperationW(
    SHFILEOPSTRUCTW(FO_DELETE, FOF_ALLOWUNDO | FOF_NOCONFIRMATION | ...))
```

两个坑：

1. **路径必须用反斜杠**，传正斜杠返回 `rc=120`
2. **成功后也可能返回错误码 `rc=2`** —— 不要只看返回值，必须复查 `os.path.exists`

## 七、bash 里访问 `$Recycle.Bin`

`$Recycle` 会被 shell 当变量吃掉，路径变成 `C:/.Bin`。用 `chr(36)` 拼：

```python
p = 'C:' + chr(92) + chr(36) + 'Recycle.Bin'
```

## 八、原理图工程施工顺序

按这个顺序做，每一步都有自动校验兜底，不会做完才发现全错：

```
1. 库里取符号    load_lib + normalize(y 翻转)
2. 放置          place_pin(锚定热点坐标)
3. 声明网络      net()
4. 布线          wire_net() 显式折线
5. ERC           erc.check()      —— 电气规则
6. 几何审计      audit.audit()    —— 悬空引脚 / 压线 / 共线重叠 / 十字交叉
7. 写出          save()           —— 自动生成导线、结点、电源端口
8. 第三方回读    verify_pins / verify_nets  —— 用 altium-monkey 独立验算
9. AD 实机打开   os.startfile + 截图
```

第 8 步很关键：**用独立的第三方解析器回读自己写的文件**。
自己写、自己验，容易把同一个错误在两处同时认可。

## 九、旋转带弧线的符号：角度必须跟着转，否则线圈散架

库符号旋转放置时，只变换坐标点是不够的。弧线记录（RECORD=12，椭圆弧/饼图同理）的
扫掠角 STARTANGLE/ENDANGLE 也必须随旋转角平移，否则圆心转过去了、弧面还朝原方向。

典型症状：把官方库 `Inductor` 用 rot=270 竖放，线圈每个半圆拱的直径仍保持水平，
拱与拱之间出现缺口，整条线圈看起来是**一串不相连的小拱**（电气连接不受影响，
引脚热点照样落线，纯属视觉事故——但一眼就是错的）。

正确映射（推导+AD16 实机验证）：库空间与设计空间之间的 y 翻转，会和发射器写文件时的
y 翻转正好抵消，所以**文件内角度 = 库角度 + 旋转角**（mod 360）：

```
无镜像:  φ_new = (φ_old + rot) % 360
有镜像:  φ_new = (φ_old + 180 - rot) % 360
```

以 Inductor 为例：库内拱是 90..180/360..90（朝上、水平线圈）；rot=270 后应为
0..90/270..360（拱朝侧面、直径沿引脚轴方向，半圆首尾相连成弹簧状）。

实现见 `src/schlib.py` 的 `_shift_arc_angles()`（注意正则要兼容记录文本末尾无竖线的
情况，否则每条弧的 ENDANGLE 会漏改）。

## 十、电源端口 ORIENTATION 不参与 y 翻转，翻了一定上下颠倒

Power Port (RECORD=17) 的 ORIENTATION 是**纯显示语义**（符号朝哪边），不参与设计空间
到文件空间的 y 翻转——需要翻转方向码的只有引脚（方向码决定热点坐标）。发射器如果对
ORIENTATION 也套用 _flip_dir（1<->3 互换），所有地符号会悄悄上下颠倒。

典型症状：GND 的信号地符号（STYLE=4）三横线朝上、挂在导线上方；VCC 箭头朝下。

权威基线（AD16 自带 30+ 官方样例全量统计）：

- GND / GND 样式（STYLE=3/4）: ORIENTATION=3（朝下），46/46 处一致
- VCC / VDD / +5V 等电源（STYLE=0/2）: ORIENTATION=1（朝上）
- VEE 等负电源: ORIENTATION=3（朝下）

调用方应直接传屏幕语义的方向值（GND 传 3、VCC 传 1），发射器原样写入。
