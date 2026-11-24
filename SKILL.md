---
name: Logisim
description: Draw, edit, render and verify Logisim .circ circuits without the GUI — building schematics from XML, measuring real pin geometry, exporting print-view PNGs, and running truth tables through Logisim's own simulator. Use for 数字逻辑/数字电路 experiments, .circ files, gate/logic diagrams, 74LS00/74LS20/74LS86 schematics, or when a circuit must open in Logisim and actually work.
---

# Logisim（2.15 / HUST 版）自动化操作手册

`.circ` 是**明文 XML**，导线就是两根坐标，**几何即连接**。
所以可以完全不碰 GUI：用脚本生成 → 审计 → 用 Logisim 自己的引擎渲染/仿真。

本 skill 的全部几何数字都是 `PinsDump` 从 Logisim `Component.getEnds()` 实测出来的，
不是猜的；换 Logisim 版本请重跑 `scripts/measure_geometry.py`。

---

## 0. 先跑这三条

```bash
cd <skill 目录>
python scripts/logisim.py env                 # 确认 java / logisim 路径能被找到
python scripts/logisim.py build-tools         # 编译 java/*.java（首次或改了 java 源码）
python scripts/logisim.py selftest            # 一条命令验证整条链路（首次装完必跑）
```

- 找不到 Logisim：设 `LOGISIM_EXE=<path\logisim-*.exe>`（**exe 可以直接当 classpath**，
  launch4j 把 jar 附在 exe 尾部，不用解包）。
- 找不到 java：设 `LOGISIM_JAVA`。裸 `java` 常解析到 1.7 JRE，报“找不到主类”且没有提示。
- 要把 skill 搬到别的项目：`python scripts/install.py --to <项目目录>`（自动放到
  `<项目>/.opencode/skills/logisim`，跳过编译产物）。
- 不确定手上是哪个分支：先看 §10 的版本差异表。

---

## 1. 标准流程（不要跳步）

```text
① 列网表      每个门用哪些脚、每个网络的点
② 排位置      左输入 → 中门列 → 右输出，列距 ≥280、行距 ≥120
③ 量几何      python scripts/logisim.py pins x.circ      ← 别手算
④ 写生成脚本  拼 XML（模板见 templates/make_circ.py）
⑤ 审计        python scripts/logisim.py audit x.circ     ← 必须 0 错误
⑥ 结构检查    python scripts/logisim.py check x.circ 电路名 --require …
⑦ 真值表      python scripts/logisim.py sim x.circ 电路名  ← 8/8 或 16/16 全对
⑧ 出图        python scripts/logisim.py render x.circ 电路名 out.png 4
⑨ 看图        检查标签压线/重叠；有问题回 ③
```

**审计和真值表都过了才算做完**，不要只看图。

---

## 2. 五条铁律

1. **几何不要猜，问 Logisim**：`logisim.py pins` 打印每个元件的 loc / 外接矩形 / 每个引脚相对 loc 的偏移。
   同一个 "NAND Gate" 在 `size=30` 和 `size=50` 下输入脚位置不同；
   `size=30` 时 AND/OR 在 `x−30`、NAND/NOR/XOR 在 `x−40`、XNOR 在 `x−50`。
   写成同一个数会短线 10～20 格，还常被文字标签挡住看不出来。
2. **导线端点必须精确落在引脚上**（同坐标）。差 1 格就是没接上，Logisim 不报错。
3. **`out` 属性恒写 `"01"`**，与输入个数无关。写 `"001"` 会
   `attribute value (001) is not valid`，headless 下表现为 `HeadlessException`。
4. **不要让 GUI 保存手写 `.circ`**：会被重排、`source` 从 `.jar` 变 `.exe`、diff 全变。
   用户手动改过的文件先备份再覆盖。
5. **导出图不要用 GUI 截图**：走 `CircExport`（Logisim「文件→导出图像」的同一段代码），
   printerView=true → 导线/门体全黑、4 倍分辨率。

---

## 3. 命令速查

| 目的 | 命令 |
|---|---|
| 环境检查 | `python scripts/logisim.py env` |
| 编译 java 工具 | `python scripts/logisim.py build-tools` |
| 端到端自检 | `python scripts/logisim.py selftest` |
| 元件/引脚/矩形 | `python scripts/logisim.py pins x.circ` |
| 几何审计 | `python scripts/logisim.py audit x.circ [电路名]` |
| 结构检查（题面约束） | `python scripts/logisim.py check x.circ 电路名 --require A:1:in --forbid-lib 5` |
| 出 PNG | `python scripts/logisim.py render x.circ 电路名 out.png 4`<br>`python scripts/logisim.py render x.circ ALL outdir 2` |
| 真值表 | `python scripts/logisim.py sim x.circ 电路名 [x,y ...]` |
| 逐拍波形 | `python scripts/logisim.py sim x.circ 电路名 [x,y] --clock CLK --ticks 8 --combo 010` |
| 查红线/电平 | `python scripts/logisim.py values x.circ 电路名 [combo] --red` |
| 装到别的项目 | `python scripts/install.py --to <项目目录>` |
| 重新实测几何 | `python scripts/measure_geometry.py` |

底层工具（需要时直接调）：
`PinsDump`（几何→TSV）、`SimTable`（真值表）、`CircExport`（PNG）、
`PinDump` / `BoundsDump` / `LibDump` / `FactoryDump` / `ToolbarDump`（人读版）。

```bash
set LOGISIM=C:\tools\logisim-hust-20200118.exe
set JAVA="C:\Program Files\Java\jdk-17\bin\java.exe"
%JAVA% -Djava.awt.headless=true -cp "%LOGISIM%;java\classes" PinsDump  in.circ out.tsv
%JAVA% -Djava.awt.headless=true -cp "%LOGISIM%;java\classes" CircExport in.circ 电路名 out.png 4
```

---

## 4. `.circ` 骨架（最小可打开）

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="2.15.0.2.jar" version="1.0">
This file is intended to be loaded by Logisim http://logisim.altervista.org
  <lib desc="#Base" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#TTL" name="2"/>
  <lib desc="#Wiring" name="3"/>
  <lib desc="#Plexers" name="4"/>
  <lib desc="#Arithmetic" name="5"/>
  <lib desc="#Memory" name="6"/>
  <lib desc="#I/O" name="7"/>
  <main name="主电路"/>
  <options>
    <a name="gateUndefined" val="ignore"/>
    <a name="simlimit" val="1000"/>
    <a name="simrand" val="0"/>
  </options>
  <mappings/>
  <toolbar> … 见 §5 … </toolbar>
  <circuit name="主电路">
    <a name="circuit" val="主电路"/>
    <a name="clabel" val=""/>
    <a name="clabelup" val="east"/>
    <a name="clabelfont" val="Dialog plain 16"/>
    <a name="clabelcolor" val="#000000"/>
    <wire from="(200,250)" to="(360,250)"/>
    <comp lib="3" loc="(200,250)" name="Pin">
      <a name="facing" val="east"/><a name="output" val="false"/>
      <a name="width" val="1"/><a name="tristate" val="false"/><a name="pull" val="none"/>
      <a name="label" val="A"/><a name="labelloc" val="north"/>
      <a name="labelfont" val="Dialog plain 16"/><a name="labelcolor" val="#000000"/>
    </comp>
  </circuit>
</project>
```

- 库编号：`0=#Base 1=#Gates 2=#TTL 3=#Wiring 4=#Plexers 5=#Arithmetic 6=#Memory 7=#I/O`
  —— 不同版本/不同文件的编号可能不同，**以本文件 `<lib … name="n">` 为准**。
- 一个 `<project>` 里可以有多个 `<circuit>`，`<main>` 决定打开时显示哪个。
- 导线必须正交（水平/垂直）。斜线能加载，但别写。
- `<toolbar/>` 留空文件也能开，但顶部工具栏是空的，用户每次都要去左侧库翻。
- 所有坐标统一加偏移（如 `+200,+140`），别贴着画布左上角——否则框选/往左上拉线都点不到。
  `CircExport` 按内容包围盒裁图，留白不会进 PNG。

---

## 5. 工具栏要写满

顺序 = 从左到右显示顺序，`lib` 必须和本文件 `<lib>` 编号一致：

| 工具 | lib | 关键属性 |
|---|---|---|
| Poke Tool / Edit Tool | 0 | 无 |
| Text Tool | 0 | text/font/halign |
| Pin（输入） | 3 | `facing="east" output="false"` |
| Pin（输出） | 3 | `facing="west" output="true"` |
| 门 | 1 | facing/size/inputs/negate0..N |
| Power / Ground | 3 | `facing` |
| Pull Resistor | 3 | `facing` `pull="0"` |
| Switch / LED | 7 | facing / color / active |

验证：`java -cp … ToolbarDump x.circ` → `toolbar size` 应 > 0。

---

## 6. 元件几何要点（完整表见 `references/02_geometry.md`）

**2 输入门，`size=30`，朝东**（`loc` = 输出）：

| 门 | 输入 x 偏移 | dy | 门体 |
|---|---|---|---|
| AND / OR | `−30` | `±10` | 30×30 |
| NAND / NOR / XOR | `−40` | `±10` | 40×30 |
| XNOR | `−50` | `±10` | 50×30 |
| NOT | `−20`（size=20）/ `−30`（size=30） | 0 | 20×18 |

- 输入数 ≥3 时**没有 y=0 的脚**：3 输入是 `−10,0,+10`；4 输入是 `−20,−10,+10,+20`。
- 门的 `label` 画在**门体里面**，挤住门形 → 位号请用单独 `Text` 放门上方。

**单脚元件（只有 `loc` 一个连接点）**：
`Power`、`Ground`、`LED`、`Probe`、`Tunnel`、`Pull Resistor`、`Constant`、`Clock`、`Button`。

- `Pin` 朝东（输入）：连接点 `loc`，方框朝左；朝西（输出）：连接点仍在 `loc`，方框朝右。
  两个 Pin 上下间距 <50 时引脚名会打架。
- **输入 Pin 是驱动器**，同一网络上不能再接开关/电源，否则多驱动变成 `E`；
  **输出 Pin 是接收器**，可以挂在电源/地上当测试点。
- `Pull Resistor` 不是两端电阻，是“把本节点弱拉到 0/1”的符号，旁边写 `10k` + 图例。
- `Switch` 是**通/断**型（断开即悬空），不能直接当 0/1 源；要手点 0/1 用 `DipSwitch`。

---

## 7. 开关：SPDT 子电路

`SPDT_SEL`（模板 `templates/spdt_sel.circ`）：**T1/T2 输入、C 输出、S 选择**。

```
+5 V ── T1 ┐
           ├─ C ──→ 门电路        S=0（扳手朝上）→ C=T1=1
GND  ── T2 ┘                      S=1（扳手朝下）→ C=T2=0
```

| 引脚 | 朝东位置 | 方向 |
|---|---|---|
| T1 | 左上 | 输入 |
| T2 | 左下 | 输入 |
| C | 右中 | 输出 |
| S | 上中 | 输入 |

坑：

- **内部必须用 2 选 1 多路选择器**（`#Plexers`，`select=1 width=1`）。
  两个传输门输出并联时，关断那一路不是干净高阻，公共端会报 `E`。
- 输出 `C` 用 `Pin(output=true, tristate=false)`；`tristate=true` 时未驱动显示 `x`，易误判没接上。
- 扳手（1 位 `DipSwitch`）要放方块**上方、朝南**；放下方朝北会“朝上却接下面那个掷”。
- 子电路是**白底**，绘制顺序 = 文件里 `<comp>` 顺序：先 `SPDT_SEL`、再扳手，否则扳手被盖住点不到。
- 旋转方块不会带着扳手转；外观无文字，方块可随便转，扳手要自己挪到新的 `S` 位置。

`SPDT`（反方向：C 输入、T1/T2 输出）适合“一个信号选两路显示”，
`SPDT_SW`（S 进、C 出）是 0/1 输入开关，用法相同。

---

## 8. 出图

`CircExport` 走 Logisim「文件 → 导出图像」：

```java
Bounds b = circ.getBounds(pg).expand(10);
gg.scale(scale, scale); gg.translate(-b.getX(), -b.getY());
proj.getSimulator().setCircuitState(state);
proj.getSimulator().step();          // 先传播一次，电源脚才显示 1
ComponentDrawContext ctx = new ComponentDrawContext(…, true);   // true = 打印视图
circ.draw(ctx, null);
```

- `printerView=true`：导线/门体全黑，无仿真着色（Pin 仍是绿色）。
- 4 倍足够放进 Word（14 cm 宽）；`scale=2` 适合快速自查。
- 正常结束必须 `System.exit(0)`，否则 AWT 线程会挂住 JVM。
- **渲染成功本身也是加载校验**：文件有错时 Logisim 弹 `JOptionPane`，
  headless 下变成 `HeadlessException`，不会静默出空白图。

---

## 9. 审计与真值表

`audit` 检查（ERROR 会让返回码变 1）：

| 项 | 含义 |
|---|---|
| 悬空端点 | 导线端点不在引脚上、不重复、也不落在线身内部 |
| 未接引脚 | 引脚既不在导线端点上、也不落在导线内部 |
| 同向重叠 | 共线且重叠的两根导线（看着像一根，实际两根，点选只中一段） |
| 穿元件体 | 导线穿过元件外接矩形内部（端点落在引脚上不算） |
| 文字压线 | Text 被导线从字身中间穿过 |
| 电源短路 | 同一网络上同时有 `Power` 和 `Ground` → **必然**是红色 E |
| 多驱动 | 两个以上输出脚同网（WARN）→ 值不同就变红 |
| 文字重叠 | 两个 Text 外接矩形互相叠（WARN）→ 打印出来糊在一起 |
| 元件同坐标 | 多个元件压在同一坐标（WARN）→ GUI 里点选互相遮挡 |
| 交叉点 | 只统计数量（INFO）；`--cross-gap N` 才把“离结点 <N”当风格提示 |

`check` 是另一类检查（不碰几何，只看题面约束）：

```bash
python scripts/logisim.py check x.circ 电路名 \
    --require "A 输入:1:in" --require "L 输出:1:out" \
    --forbid-lib "#Arithmetic" --forbid "Adder,Subtractor" \
    --max-comps 40 --no-halt
```

- `--require LABEL:WIDTH:in|out`：必须有这个标签、这个位宽、这个方向的 `Pin`。
- `--forbid-lib`：写 `#库名` 或 desc 号（`#Gates`=1、`#TTL`=2、`#Memory`=6…），
  用来证明“只用了 74LS00”。
- `--max-comps / --no-halt`：交付件别太大、别留验证用的 halt。
- 电路名省略时取 `<main>`。

`sim` 用 **Logisim 自己的 Propagator** 跑真值表（不是自己写的求值器）：

- 驱动源自动选：有 1 位 `DipSwitch` 就用它（按 y 从上到下 = A、B、C…），
  否则退化用输入 `Pin`。
- 探测点不写就取所有 `LED` + 输出 `Pin`。
- **输出里的 0/1 是器件原始值**：`SPDT_SEL` 里 `S=0 → C=+5V=1`，
  所以 `DipSwitch` 的原始值 **0 = 扳手朝上 = 逻辑 1**，看表时别读反。
- 位串**从左到右 = 开关从上到下**，`sim` 和 `values` 用同一套顺序：
  `sim` 的 `010 -> 1` 必须等于 `values x.circ 电路名 010` 里探测点读到的那一位。

### 9.1 时序电路：每个上升沿一行

组合表扫不出计数器/寄存器，用 `--clock` 手动打拍：

```bash
python scripts/logisim.py sim 计数器.circ 计数器 500,300 --clock CLK --ticks 8
```

```text
clock(CLK)(400,320)  ticks=8  combo=0…  data:  probes: 500,300
t0 -> 0000
t1 -> 0001
t2 -> 0010
...
```

- `--clock LABEL`：把这个**标签**的 1 位输入（`Pin` 或 `DipSwitch`）当时钟，
  其余 1 位输入当数据。
- 每一拍 = 先拉低并传播、再拉高并传播，**采样在上升沿之后**，
  所以 `trigger=rising` 的寄存器/计数器直接对得上。
- `--combo 010`：其余数据输入固定成这个位串（顺序同上：从上到下）。
  不写就全 0。
- **必须用手动输入当时钟**（`Pin` / `DipSwitch`）。`Clock` 元件由仿真线程自己振，
  不在支持范围；用 `Clock` 时命令会直接报错提示。
- 只能驱动 1 位 `DipSwitch`：多位拨码（`NSwitches>1`）不参与自动驱动，
  数据位请用输入 `Pin`。

---

## 10. 版本差异（先确认你用的是哪一版）

本 skill 的数字全部来自 **Logisim 2.15.0.2 HUST 版**（`logisim-hust-*.exe`）。
网上大部分 Logisim 教程是另外两个分支，抄之前先对一下：

| | 2.15 HUST 版（本 skill） | Logisim 2.7.1（官方经典版） | Logisim-evolution |
|---|---|---|---|
| `.circ` 顶层 | `source="2.15.0.2.jar"` | `source="2.7.1"` | `source="..."`（版本更高） |
| 库编号 | **每份文件自己声明**，以 `<lib name="n">` 为准 | 同上 | 同上 |
| 输出 Pin | `<a name="output" val="true"/>` | 同 2.15 | `<a name="type" val="output"/>`（旧属性会自动转换） |
| `Hex Digit Display` | **没有** `decimalPoint` 属性 | 无 | 有 `decimalPoint`，且 DP 脚在 `loc+(20,0)` |
| 命令行真值表 | `-tty stats` 可用；**`-tty table` 实测输出为空，别依赖** | `-tty table` 可用 | `--tty table` 可用 |
| 时序测试向量 | 无 | `-test <电路> <向量文件>` | `-w <电路> <向量文件>` |
| 本 skill 的 `pins/audit/sim/values` | ✅ | ⚠ 几何可能不同，先 `measure_geometry.py` | ❌ 属性/几何都不同，只能当思路参考 |

**跨版本抄示例的三种翻车**：

1. 抄 `type="output"` → 2.15 不认，Pin 变成输入（多驱动、红线）。
2. 抄 `decimalPoint="false"` → 2.15 没有这个属性，加载失败（`HeadlessException`）。
3. 抄 `-tty table` 的结果当验证 → 2.15 的 HUST 分支实测打印空表，**必须用 `sim`**。

换版本时第一件事：`python scripts/measure_geometry.py` 重新量，再 `logisim.py audit` 现有文件。

---

## 11. 参考文件

| 文件 | 内容 |
|---|---|
| `references/01_circ_format.md` | `.circ` XML 完整结构、属性表、子电路外观（`<appear>`/`<circ-port>`） |
| `references/02_geometry.md` | 全部元件引脚几何实测表（脚本生成，最权威） |
| `references/03_layout.md` | 版面规则：走线、交叉、结点、标签、电源、开关+LED |
| `references/04_render_check.md` | 渲染细节 + 审计实现 + 常见误报 |
| `references/05_pitfalls.md` | 症状 → 原因 → 修法 速查表 |
| `references/06_exp_notes.md` | 实验一/二/三的实际做法与可复用文件索引 |
| `templates/make_circ.py` | Python 生成器骨架（Circuit 类 + 工具栏 + 元件函数） |
| `templates/spdt_sel.circ` | 可直接当库加载的单刀双掷子电路 |

---

## 12. 交付前检查清单

- [ ] `logisim.py audit` 错误项 = 0
- [ ] `logisim.py audit` 里 `电源短路` / `多驱动` 都是 0
- [ ] 交叉点数量自己看一眼（圆点=连、无点=交叉；间距只是美观，`--cross-gap` 可选）
- [ ] 所有门的输入坐标按 §6 的偏移写对
- [ ] `out="01"`
- [ ] 每个引脚都有线，线端点无悬空
- [ ] 线没穿门体，文字没压线
- [ ] 输入 Pin 没和开关/电源同网
- [ ] 电源/地画了，写了 `+5 V` / `GND`
- [ ] 门上方有位号+型号+逻辑式，端子旁有芯片引脚号
- [ ] `logisim.py sim` 真值表全对（注意 0=上=1）
- [ ] PNG 4 倍、黑白打印视图、无裁边
