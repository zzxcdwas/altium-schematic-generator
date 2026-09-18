---
name: altium-schematic-generator
description: 用 Python 程序生成 Altium Designer 原生原理图（.SchDoc）与工程（.PrjPCB），元器件直接从 AD 官方库取，支持层次化设计。当用户要求"用脚本画原理图""自动生成 SchDoc""批量出图""反向生成 Altium 文件""AD 画电路"时使用。含 .SchDoc 二进制格式规范、OLE 复合文档写入、引脚热点规则、ERC/几何审计、第三方解析器交叉校验全流程。
agent_created: true
---

# Altium Designer 原理图程序化生成

## 什么时候用

用户想让 AD 里出现一张画好的原理图（课设、批量出图、参数化生成），
而手上**没有** Altium API / 插件，也没人盯着鼠标点点点。

不要试图驱动 AD 的界面 —— 那些路全是死路（见 `docs/pitfalls.md`）。
正确做法：**直接按原生格式写出 `.SchDoc`，再让 AD 打开。**

## 铁律

**元器件绝对不能自己画。** 一律从 Altium 官方库（`.SchLib` / `.IntLib`）取现成符号，
用户所在课程/企业库没有的，就从 AD 自带库里找同类件，**不要自绘任何符号线条**。

## 标准流程

```
1. 探热点      tools/probe_library_hotspots.py   拿到元件的真实引脚坐标
2. 放置        sch.place_pin(锚定热点)          别手算符号原点偏移
3. 声明网络    sch.net(); sch.wire_net()        显式折线，紧密度才可控
4. ERC         src/erc.py          check()      电气规则：未连/单端/驱动冲突
5. 几何审计    src/audit.py        audit()      悬空脚/异网压线/共线重叠/十字交叉
6. 写出        sch.save()                       自动补导线、结点、电源端口
7. 第三方回读  verify_pins/nets/hierarchy       用 altium-monkey 独立验算
8. AD 实机     os.startfile(path) + 截图
```

第 7 步不能省：自己生成、自己验，会把同一个错误在两处同时认可。
必须用**独立的第三方解析器**回读磁盘文件做交叉验证。

## 三条最容易出错的规则

1. **电气连接点 = `LOCATION + 方向向量 × PINLENGTH`**
   引脚记录里的 LOCATION 是紧贴本体的那一端，不是连接点。
   连错会导致"线画上去了但 AD 认为没连通"。

2. **PINCONGLOMERATE 的方向位只能写一次**
   调用方传额外位时必须屏蔽低 2 位：`extra & 0xFC`。
   方向码由发射器在 y 翻转**之后**写入。写两次会让朝上引脚偏移 2 倍脚长。

3. **`.PrjPCB` 顶层段名必须是 `[Design]`**
   写成 `[Design_Project]` 能被加载，但成员一个都不认（显示 no documents）。

详见 `docs/pitfalls.md` 与 `docs/schdoc-format.md`。

## 快速上手

```python
import sys; sys.path.insert(0, "src")
import sch_build

DEV = "Miscellaneous Devices.IntLib"
sch = sch_build.Schematic(width=300, height=220, title="demo")

sch.place_pin("C1", "Cap", DEV, "1", 100, 60)     # 1 号脚热点钉在 (100,60)
sch.net("GND", ("C1", "2"))
sch.wire_net("GND", [[(100, 85), (100, 140)]])
sch.power_port("GND", 100, 140)
sch.save("out/demo.SchDoc")
```

完整可跑示例见 `examples/01_minimal_schematic.py`。

## 层次化设计

顶层图纸符号 + 子图端口，三层结构：

```
Top_Level.SchDoc    RECORD=15 图纸符号 + RECORD=16 入口 + 互联导线
  ├ S1.SchDoc       RECORD=18 端口 P1/P2
  └ S2.SchDoc       RECORD=18 端口 P3/P4
```

**符号里写的子图文件名必须真实存在**，否则 AD 编译报"找不到子图"。

```python
sch.hier_symbol(80, 80, 180, 90, "S1", "S1.SchDoc", [("P1", 1, 2), ("P2", 1, 4)])
sch.hier_symbol(340, 80, 140, 90, "S2", "S2.SchDoc", [("P3", 0, 2), ("P4", 0, 4)])
sch.hier_wire("LINK", [[(260, 100), (340, 100)]])
```

## 让 AD 打开（重要）

```python
os.startfile(r"out\Top_Level.SchDoc")   # ✅ 走 Shell 关联，等价双击
subprocess.Popen([ad_exe, path])        # ❌ 进程级传参会卡住
```

## 目录

| 路径 | 内容 |
|---|---|
| `src/` | 核心：OLE 读写、记录发射、库解析、构建器、ERC、几何审计、第三方校验 |
| `docs/schdoc-format.md` | **`.SchDoc` 二进制格式规范**（记录结构、热点规则、位域） |
| `docs/prjpcb-format.md` | 工程文件格式与模板 |
| `docs/pitfalls.md` | 踩坑清单：外部控制的死路、陷阱、推荐施工顺序 |
| `docs/verified-parts.md` | 常用官方库件热点实测表（可直接查表布局） |
| `examples/` | 最小示例、多谐振荡器、数码管译码、层次化四张图 |
| `tools/` | 热点探测器、PrjPCB 生成器、Windows 回收站助手 |

## 环境

```bash
pip install -r requirements.txt
# 可选，用于第三方交叉校验
pip install altium-monkey olefile
```

库路径通过环境变量 `ALT_LIB_ROOT` 指定，省略时自动探测常见安装位置：
```bash
python src/config.py     # 查看当前解析到的配置
```
