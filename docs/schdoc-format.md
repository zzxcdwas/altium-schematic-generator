# `.SchDoc` 原生格式规范

> 本文所有结论都在 **Altium Designer 16.1.12** 上实机验证过（生成 → AD 打开 → 截图 → 第三方库回读），
> 并以 AD 自带样例 `Examples/Bluetooth Sentinel/*.SchDoc` 交叉比对。

## 1. 容器：OLE2 复合文档

`.SchDoc` 是一个 OLE2/CFB（Compound File Binary）文件，内含若干流：

| 流名 | 内容 |
|---|---|
| `FileHeader` | **主数据**：全部记录序列 |
| `Storage` | 固定内容 `\|HEADER=Icon storage\|WEIGHT=0` |
| `__Previews` | 缩略图（可选，AD 自己会重建，不写也能正常打开） |

### 记录结构

`FileHeader` 流内是一条接一条的记录：

```
<uint16 LE  长度><0x00><uint8 类型><payload>
```

* **长度**：payload 的字节数
* **第二个字节**：恒为 `0x00`
* **类型**：属性记录为 `0`，二进制图像数据为 `1`

当类型为 `0` 时，payload 是一段 ASCII/UTF-8 文本：

```
|KEY=VAL|KEY=VAL|...|<0x00>
```

**长度 = 文本字节数 + 1**（因为末尾那个 `\0` 也要算进去）。

### HEADER 记录必须声明 Binary

流的第一条记录必须是 HEADER，并且**必须包含 `Binary=1`**（否则 AD 打开时报格式错误）：

```
|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0
|WEIGHT=...|MINORVERSION=2|BINARY=1|UNIQUEID=...
```

## 2. 记录类型速查表

| RECORD | 含义 | 关键字段 |
|---|---|---|
| 1 | 元件（Component） | `LIBREFERENCE`, `DESIGNATOR`, `AREACOLOR` |
| 2 | 引脚（Pin） | `NAME`, `DESIGNATOR`, `PINCONGLOMERATE`, `PINLENGTH` |
| 4 | 文本字符串 | `TEXT`, `FONTID`, `JUSTIFICATION` |
| 6 / 7 | 多边形 / 椭圆 | `LINES`, `POINTS` |
| 11 | 贝塞尔曲线 | |
| 13 / 14 | 矩形 / 圆角矩形 | `LOCATION.X/Y`, `CORNER.X/Y` |
| **15** | **图纸符号**（Sheet Symbol） | `LOCATION.X/Y`, `XSIZE`, `YSIZE` |
| **16** | **图纸入口**（Sheet Entry） | `NAME`, `SIDE`, `DISTANCEFROMTOP` |
| 17 | 电源端口（Power Port） | `NET`, `STYLE`, `ORIENTATION` |
| **18** | **端口**（Port，层次化用） | `NAME`, `WIDTH`, `IOTYPE` |
| 25 | 网络标签（Net Label） | `TEXT` |
| 27 | 导线（Wire） | `X1..Xn`, `Y1..Yn` |
| 28 | 图形线（无电气属性） | |
| 29 | 结点（Junction） | `LOCATION.X/Y` |
| 32 | 子标签：符号名 | `TEXT` |
| 33 | 子标签：引用的子图文件名 | `TEXT` |
| 34 | 参数（Parameter） | `NAME`, `TEXT` |
| 41 | 实现（Implementation） | |

## 3. 坐标系 —— 最容易踩的坑

**库空间 y 轴向上，设计空间 y 轴向下。**

库文件（`.SchLib` / `.IntLib`）里的符号用数学坐标系（y 向上）保存；而 `.SchDoc`
里所有几何都用屏幕坐标系（y 向下）。因此从库里取出符号后必须做一次翻转：

```python
y_design = -y_library      # 一次性在加载时完成
```

如果不翻转，画出来的图会上下颠倒；如果翻转两次，引脚会跑到元件本体另一侧。

### 方向码

引脚方向用两位编码，`0=右 1=上 2=左 3=下`（库空间语义）。翻转到设计空间时 `1` 和 `3` 互换。

## 4. 引脚热点：电气连接点到底在哪

**这是整个 pipeline 最关键的一条规则。**

引脚记录里：

* `LOCATION.X/Y` —— 是**引脚紧贴元件本体的那一端**（不是电气连接点）
* 电气连接点（extends / hotspot）= `LOCATION + 方向向量 × PINLENGTH`

```
hot = (loc.x + dx * pinlength, loc.y + dy * pinlength)
```

> 验证方法：拿一个 AD 自己导出的原理图，把每根导线的端点与所有候选点做匹配——
> **164/164 个导线端点命中 `LOCATION + dir*PINLENGTH`，命中 `LOCATION` 的为 0。**

所以布线时一定要连到热点，而不是引脚本体坐标。连到本体坐标会出现
「线端点压在元件身上、AD 认为没连上」的假连接。

## 5. PINCONGLOMERATE 的位域

`PINCONGLOMERATE` 是一个位掩码：

| 位 | 值 | 含义 |
|---|---|---|
| bit0-1 | 0/1/2/3 | **方向码**（翻转后的） |
| bit2 | 0x04 | 显示网络名 |
| bit3 | 0x08 | 显示引脚名 |
| bit4 | 0x10 | 显示引脚编号 |
| bit5 | 0x20 | AD 真实文件里恒定的标记位 |

真正 AD 写出的值形如 `32`、`34`、`42`。

### ⚠️ 致命陷阱

**方向位只能由「翻转之后」的那一次写入决定。** 如果上层调用方自己也把方向码
OR 进去，而底层发射器在翻转后又 OR 一次，两边的方向码会叠加：

```python
# 错误：调用方带了方向，发射器翻转后又加一次
conglomerate = (direction | caller_extra) & 0xFF

# 正确：发射器用已翻转的 direction，调用方的额外位屏蔽掉低 2 位
conglomerate = (direction | (caller_extra & 0xFC)) & 0xFF
```

症状：所有「朝上」的引脚，其 `connection_point` 会偏离 **2 倍引脚长度**，
第三方解析器回读时发现引脚没落在导线上。

## 6. 图纸符号三层结构（层次化）

层次化图纸由三层记录组成：

```
RECORD=15  图纸符号本体      LOCATION=左上角, XSIZE, YSIZE
  └ RECORD=32  符号名         TEXT=S1              (作为 15 的子记录)
  └ RECORD=33  子图文件名     TEXT=S1.SchDoc       (作为 15 的子记录)
  └ RECORD=16  图纸入口       NAME/SIDE/DISTANCEFROMTOP
```

* **LOCATION 是左上角**，向下延伸 `YSIZE`（注意不是中心，也不是左下角）
* 入口 `SIDE`：`0=左 1=右 2=上 3=下`
* 入口 `DISTANCEFROMTOP`：**以 10 为单位**从顶边往下数
* 入口的连接点 = 对应边上的那个点

### 端口 RECORD=18

* `LOCATION` 是端口本体的**左端**，向右延伸 `WIDTH`
* **两端都是连接点**（左端 `LOCATION`，右端 `LOCATION + WIDTH`）
* `IOTYPE`：`1=In 2=Out 3=IO`

子图里放端口（18），顶层图纸符号上放入口（16），两边同名即连通。

## 7. DISPLAYMODE

部分多形态符号（典型是 `74LS47` 这类有 DeMorgan 等价体的芯片）的真实图形
**只存在于 `DISPLAYMODE=1`**，发射时必须显式设置，否则 AD 里画出来是个空框。

```python
props["DISPLAYMODE"] = "1"
```

## 8. 大小写陷阱

不同库写出的字段名大小写不一致：

* `Miscellaneous Devices.IntLib` 写 `INDEXINSHEET`
* 某些课程库写 `IndexInSheet`

如果按大小写敏感去「追加」字段，会写出**同名字段出现两次**的记录，
严格的解析器（如 altium-monkey）会直接以
`duplicate field INDEXINSHEET` 报错拒绝整个文件。
正确做法是**按大小写不敏感查找并替换**。
