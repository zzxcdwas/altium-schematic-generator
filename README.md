# altium-schematic-generator

> **Generate native Altium Designer `.SchDoc` schematics from Python — no Altium automation API required.**
>
> 用 Python 直接生成 Altium Designer 原生原理图文件。元器件全部取自 AD 官方库，
> 支持层次化设计（图纸符号 / 入口 / 端口），自带 ERC、几何审计和第三方解析器交叉校验。

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Altium](https://img.shields.io/badge/Altium%20Designer-16.1%20verified-orange.svg)](https://www.altium.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**English:** A pure-Python toolkit that writes Altium Designer's native binary `.SchDoc` (OLE2 compound
file) directly to disk — no COM, no Altium automation, no Altium install needed to generate.
Parts are taken from Altium's official `.SchLib` / `.IntLib` libraries, hierarchical designs
(sheet symbols / sheet entries / ports) are supported, and every output can be cross-checked by
ERC, a geometric audit, and an independent third-party parser ([altium-monkey](https://pypi.org/project/altium-monkey/)).
Also included: reverse-engineered format documentation for `.SchDoc` and `.PrjPCB`, and a catalog of
known pitfalls that cost real debugging time.

> 中文简介：纯 Python 写出 AD 原生二进制原理图，不需要 COM / 自动化接口，也不需要装 AD 就能生成。
> 元件取自 AD 官方库，支持层次化设计，输出可用 ERC、几何审计和第三方解析器三重校验。
> 另附 `.SchDoc` / `.PrjPCB` 逆向格式文档与踩坑清单。

---

## 它解决什么问题

想在 Altium Designer 里得到一张画好的原理图，通常只有两条路：手动拖拽，或者折腾 AD 的自动化接口。

**第二条路是死路。** 我们在 AD16.1.12 上逐条验证过：

| 尝试过的路径 | 结果 |
|---|---|
| COM / `WScript.Shell` / PowerShell `Add-Type` | 被安全策略拦截 |
| `DXP.EXE /RunScript:file` | AD16 不支持，进程起来就退 |
| `dxpProcess:` / `dxp:` URL 协议 | 传参无反应 |
| 鼠标键盘注入（`SendInput` / `keybd_event`） | API 返回成功但目标无响应 |
| `PostMessage` 键盘消息 | AD 菜单自绘，不响应 |
| 导出 ASCII `.SchDoc` 再改 | **AD 只导出、不读入** |

本项目的做法：**绕过 AD，直接在磁盘上写出它的原生格式**，然后让 AD 打开。

---

## 快速开始

```bash
git clone https://github.com/zzxcdwas/altium-schematic-generator.git
cd altium-schematic-generator
python examples/01_minimal_schematic.py
```

产出 `out/01_minimal.SchDoc` —— 直接用 Altium Designer 打开即可。
（生成不需要安装 Altium；只有"想在 AD 里看效果"这一步才需要。）

### 30 行代码出一张图

```python
import sys; sys.path.insert(0, "src")
import sch_build

DEV = "Miscellaneous Devices.IntLib"          # AD 自带库
sch = sch_build.Schematic(width=300, height=220, title="demo")

sch.place_pin("C1", "Cap", DEV, "1", 100, 60)  # 1 号脚热点钉在 (100,60)
sch.place_pin("C2", "Cap", DEV, "1", 180, 60)

sch.net("IN",  ("C1", "1"), ("C2", "1"))
sch.net("GND", ("C1", "2"), ("C2", "2"))
sch.wire_net("IN",  [[(100, 60), (180, 60)]])
sch.wire_net("GND", [[(100, 85), (100, 140)],
                     [(180, 85), (180, 140)],
                     [(100, 140), (180, 140)]])
sch.power_port("GND", 140, 140)

sch.save("out/demo.SchDoc")                    # 自动补导线、结点、电源端口
```

---

## 三个核心设计

### 1. 元器件一律取自官方库

**代码里没有一条自绘符号线条。** 所有元件由 `.SchLib` / `.IntLib` 现成符号变换而来。

布局时不手算符号原点偏移，而是**锚定引脚热点**：

```python
sch.place_pin("Q1", "9013-DIP", "04-三极管.SchLib", "3", 220, 140)   # 把 C 极钉在 (220,140)
```

### 2. 自己生成，自己不算数 —— 用第三方解析器回读

自己写生成器、自己写校验，会把同一个错误在两处同时认可。所以校验环节用**独立的**开源解析器
[altium-monkey](https://pypi.org/project/altium-monkey/) 回读磁盘上的文件：

```
$ python src/verify_pins.py out/Top_Level.SchDoc
  图4-74: 36/36 引脚落在导线上, 悬空 0
  图4-75: 96/96 引脚落在导线上, 悬空 0

$ python src/verify_nets.py out/Top_Level.SchDoc
  并查集独立复算: 10/10 网络一致, 40/40 网络一致, 短路 0
```

### 3. 施工顺序带校验兜底

```
探热点 → 放置 → 声明网络 → 布线 → ERC → 几何审计 → 写出 → 第三方回读 → AD 实机打开
```

每一步都有自动检查，不会画完一整张图才发现某一类错误从头错到尾。

---

## 目录结构

```
altium-schematic-generator/
├── src/                        核心库
│   ├── config.py               路径配置（环境变量 / 自动探测）
│   ├── cfb_reader.py           OLE2 复合文档读取
│   ├── cfb_writer.py           OLE2 复合文档写入
│   ├── sch_gen.py              记录发射器（导线/引脚/端口/图纸符号…）
│   ├── schlib.py               .SchLib / .IntLib 符号解析
│   ├── sch_pack.py             OLE 打包
│   ├── sch_build.py            构建器：放置 / 网络 / 布线 / 保存
│   ├── erc.py                  电气规则检查
│   ├── audit.py                几何审计（悬空/压线/重叠/交叉）
│   ├── verify_pins.py          第三方回读：引脚是否落在导线上
│   ├── verify_nets.py          第三方回读：并查集复算网表
│   └── verify_hierarchy.py     第三方回读：层次化入口与端口
├── docs/
│   ├── schdoc-format.md        ★ .SchDoc 二进制格式规范
│   ├── prjpcb-format.md        ★ 工程文件格式与模板
│   ├── pitfalls.md             ★ 踩坑清单
│   └── verified-parts.md       ★ 官方库件热点实测表
├── examples/
│   ├── 01_minimal_schematic.py       最小上手
│   ├── build_lab.py                  多谐振荡器 + 数码管译码
│   └── build_hier.py                 层次化设计（顶层 + 两张子图）
├── tools/
│   ├── probe_library_hotspots.py     探测任意元件的引脚热点
│   ├── make_project.py               生成 .PrjPCB 工程
│   └── recycle.py                    Windows 回收站助手
└── SKILL.md                    Agent / LLM 使用的指令入口
```

---

## 格式规范（节选）

`.SchDoc` 是 OLE2 复合文档，主数据在 `FileHeader` 流，由记录序列构成：

```
<uint16 LE 长度><0x00><uint8 类型><payload>
```

属性记录的 payload 是 `|KEY=VAL|KEY=VAL|...|<0x00>`，**长度 = 文本字节数 + 1**。

### 最关键的一条：电气连接点不在这里

引脚记录里的 `LOCATION` 是**紧贴元件本体的那一端**。真正的电气连接点是：

```
hot = LOCATION + 方向向量 × PINLENGTH
```

> 验证：拿 AD 自己导出的原理图，把每个导线端点与所有候选点做匹配 ——
> **164/164 命中 `LOCATION + dir×PINLENGTH`，命中 `LOCATION` 的为 0。**

连到 LOCATION 会得到"线画上去了但 AD 认为没连通"的假连接。

完整规范见 [`docs/schdoc-format.md`](docs/schdoc-format.md)。

---

## 层次化设计

```
Top_Level.SchDoc          RECORD=15 图纸符号 + RECORD=16 入口 + 互联导线
  ├─ S1.SchDoc            RECORD=18 端口 P1 / P2
  └─ S2.SchDoc            RECORD=18 端口 P3 / P4
```

```python
sch.hier_symbol(80, 80, 180, 90, "S1", "S1.SchDoc", [("P1", 1, 2), ("P2", 1, 4)])
sch.hier_symbol(340, 80, 140, 90, "S2", "S2.SchDoc", [("P3", 0, 2), ("P4", 0, 4)])
sch.hier_wire("LINK_TOP", [[(260, 100), (340, 100)]])
sch.hier_wire("LINK_BOT", [[(260, 120), (340, 120)]])
```

⚠️ **符号里写的子图文件名必须真实存在**，否则 AD 编译时报"找不到子图"。

---

## 环境要求

| 项目 | 说明 |
|---|---|
| Python | 3.8+（核心生成不依赖任何第三方包） |
| Altium Designer | 用于打开验证，本项目在 16.1.12 上验证通过 |
| `altium-monkey` | 可选，第三方交叉校验时需要 |
| `olefile` | 可选，读取已有文件时方便 |

```bash
pip install -r requirements.txt
```

### 库路径

通过环境变量指定 Altium 原理图库目录：

```bash
export ALT_LIB_ROOT="D:/SoftWare/AD16/Documents/Library"   # Linux / macOS
set ALT_LIB_ROOT=D:\SoftWare\AD16\Documents\Library        # Windows

python src/config.py        # 查看当前解析结果
```

省略时会自动探测常见安装位置。

---

## 示例自带的完整案例

| 示例 | 内容 | 规模 |
|---|---|---|
| `01_minimal_schematic.py` | 两电容并联，只用 AD 自带库 | 2 器件 / 2 网络 |
| `build_lab.py` (lab1) | 多谐振荡器 | 17 器件 / 10 网络 / ERC 0 错 0 警 |
| `build_lab.py` (lab2) | 74LS47 数码管译码 | 9 器件 / 40 网络 / ERC 0 错 0 警 |
| `build_hier.py` | 层次化：顶层 + 2 子图 + 完整版 | 46 引脚 / 4 端口 / 4 入口全落线 |

```bash
python examples/01_minimal_schematic.py
python examples/build_lab.py            # 跑 lab1 + lab2
python examples/build_hier.py           # 生成四张层次化图纸
```

> `build_lab.py` 的部分元件来自常见中文课程库（如 `01-电阻-电容-电感.SchLib`）。
> 如果你的机器上没有，文档 [`docs/verified-parts.md`](docs/verified-parts.md)
> 给出了等价的 AD 自带库替代件，或直接用 `tools/probe_library_hotspots.py` 探测你手头的库。

---

## 常见问题

**Q：生成的图 AD 打不开？**
绝大多数是 HEADER 记录没写 `BINARY=1`，或者某条记录长度算错（记住要 +1 算结尾 `\0`）。
见 [`docs/schdoc-format.md`](docs/schdoc-format.md) §1。

**Q：打开是个空框？**
多形态符号（74LS47 这类）的图形只存在于 `DISPLAYMODE=1`，必须显式设置。

**Q：AD 里元件底座连不上线？**
连到 `LOCATION` 而不是热点了。见上文"电气连接点不在这里"。

**Q：引脚整体歪了 / 上下颠倒？**
库空间 y 向上、设计空间 y 向下，翻转要么没做、要么做了两次。
本项目在 `load_lib` 时统一翻转一次。

**Q：工程打开显示 no documents？**
`.PrjPCB` 顶层段名写成 `[Design_Project]` 了，必须是 `[Design]` 且每个文档一个 `[DocumentN]` 段。

---

## 许可

MIT License，见 [LICENSE](LICENSE)。

## 致谢

格式规范的推导过程中借鉴了社区里关于 Altium 文件格式的各类逆向笔记，
但所有结论均在真实 AD16.1.12 环境实机验证，并与 AD 自带样例逐字段交叉比对。
第三方交叉校验使用 [altium-monkey](https://pypi.org/project/altium-monkey/)。
