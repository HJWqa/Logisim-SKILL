# `.circ` 文件格式（Logisim 2.15 / HUST 版）

> 全部结论来自实际读写 `实验二_全部电路.circ`、`实验三_全部电路.circ`、
> 以及 GUI 保存的 `empty.circ`。

---

## 1. 容器

`.circ` **就是纯文本 XML**，没有压缩、没有二进制段（对比 Multisim `.ms14` 是 LZSS+Huffman 容器）。

```
file(1) → "XML 1.0 document, UTF-8 Unicode text"
```

可以直接 `git diff`、正则替换、脚本生成。**这是 Logisim 最大的优势**：
坐标是字面值，改坐标不会触发引擎重排（Multisim 会）。

### 1.1 source 属性

| 保存方式 | `<project source="…">` |
|---|---|
| GUI 另存 | `2.15.0.2.exe` |
| 手写 | `2.15.0.2.jar` |

两者都能加载。GUI 保存会**重排整份 XML**（缩进、属性顺序、坐标顺序、空格），
所以手写源文件不要用 GUI 保存，否则 diff 全变。

---

## 2. 顶层结构

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="2.15.0.2.jar" version="1.0">
This file is intended to be loaded by Logisim http://logisim.altervista.org
  <lib desc="#Base" name="0"> … tool 定义 … </lib>
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
  <mappings>
    <tool lib="0" map="Button2" name="Poke Tool"/>
    <tool lib="0" map="Button3" name="Menu Tool"/>
    <tool lib="0" map="Ctrl Button1" name="Menu Tool"/>
  </mappings>
  <toolbar> … </toolbar>
  <circuit name="主电路"> … </circuit>
  <circuit name="另一个电路"> … </circuit>
</project>
```

第 3 行的注释文本严格上是 project 的文本节点，**保留**（照抄已有文件最稳）。

### 2.1 库编号

**每份文件自己声明**，不同文件可能不同（`empty.circ` 是 `0=#Wiring … 7=#Base`）：

| 常见编号 | 库 | desc |
|---|---|---|
| 0 | Base | `#Base`（Text Tool 等） |
| 1 | Gates | `#Gates` |
| 2 | TTL | `#TTL` |
| 3 | Wiring | `#Wiring` |
| 4 | Plexers | `#Plexers` |
| 5 | Arithmetic | `#Arithmetic` |
| 6 | Memory | `#Memory` |
| 7 | I/O | `#I/O` |

`comp` 的 `lib` 属性、`tool` 的 `lib` 属性、`mappings` 的 `lib` 都指这个编号。
**不要照抄网上例子**——先用 `LibDump` 确认本文件的编号。

### 2.2 options

| 名字 | 值 | 含义 |
|---|---|---|
| `gateUndefined` | `ignore` / `error` / `up` / `down` | 未定义输入怎么处理 |
| `simlimit` | 1000 | 仿真频率上限 |
| `simrand` | 0 | 随机种子 |

---

## 3. circuit

```xml
<circuit name="半加器">
  <a name="circuit" val="半加器"/>
  <a name="clabel" val=""/>
  <a name="clabelup" val="east"/>
  <a name="clabelfont" val="Dialog plain 16"/>
  <a name="clabelcolor" val="#000000"/>
  <wire from="(260,200)" to="(300,200)"/>
  <comp lib="1" loc="(340,200)" name="NAND Gate"> … </comp>
</circuit>
```

- `clabel` 是子电路显示在父图上的名字；主电路填空。
- **绘制顺序 = 元素顺序**（后画的盖住先画的）。子电路是白底，
  所以“先放子电路、再放压在它上面的开关”。
- 导线顺序无所谓；Logisim 读入后统一建网。

### 3.1 comp

```xml
<comp lib="1" loc="(x,y)" name="NAND Gate">
  <a name="facing" val="east"/>
  <a name="size" val="30"/>
  <a name="inputs" val="2"/>
  <a name="out" val="01"/>
  <a name="label" val=""/>
  …
</comp>
```

| 属性 | 说明 |
|---|---|
| `loc` | 元件锚点，**总是必填** |
| `name` | 工厂名（`FactoryDump` / `LibDump` 查） |
| `facing` | `north`/`south`/`east`/`west`，朝哪边"看"，即输出方向 |
| `size` | 门体大小，**只接受 20/30/50/70**（20 只给 NOT/Buffer） |
| `inputs` | 门输入个数 2..10；≥11 加载失败 |
| `out` | **恒为 `"01"`** |
| `negate0..N` | 每个输入脚取反（画小圈） |
| `width` | 位宽，默认 1 |
| `label` / `labelfont` / `labelcolor` / `labelloc` | 标签 |

> `out="001"` → `attribute value (001) is not valid`。
> headless 下这条错误会变成 `HeadlessException`（见 §7）。

### 3.2 wire

```xml
<wire from="(x1,y1)" to="(x2,y2)"/>
```

- 必须正交（`x1==x2` 或 `y1==y2`）。
- 连接规则：
  - 端点落在引脚上 → 连上
  - 端点落在另一根线的**内部** → T 接，连上，自动画实心圆点
  - 两根线在**内部**相交 → 十字交叉，**不连**，没有圆点
  - 引脚落在导线内部 → 连上（不止端点，整条线都算）
- 没有“junction 对象”这种东西，结点是渲染时算出来的。

---

## 4. 工具栏

```xml
<toolbar>
  <tool lib="0" name="Poke Tool"/>
  <tool lib="0" name="Edit Tool"/>
  <sep/>
  <tool lib="0" name="Text Tool">
    <a name="text" val=""/>
    <a name="font" val="Dialog plain 16"/>
    <a name="color" val="#000000"/>
    <a name="halign" val="center"/>
    <a name="valign" val="base"/>
  </tool>
  <tool lib="3" name="Pin"> … 输入脚属性 … </tool>
  <tool lib="3" name="Pin"> … 输出脚属性 … </tool>
  <sep/>
  <tool lib="1" name="NAND Gate"> … 门属性 … </tool>
  <sep/>
  <tool lib="3" name="Power"> <a name="facing" val="north"/> </tool>
  <tool lib="3" name="Ground"> <a name="facing" val="south"/> </tool>
  <tool lib="3" name="Pull Resistor">
    <a name="facing" val="north"/><a name="pull" val="0"/>
  </tool>
  <tool lib="7" name="Switch"> … </tool>
  <tool lib="7" name="LED"> … </tool>
</toolbar>
```

`<sep/>` 是分隔线。`<toolbar/>` 留空能打开但顶栏没东西。
验证：`ToolbarDump x.circ`（打印 `proj.getOptions().getToolbarData()`，空的是 `size: 0`）。

---

## 5. 子电路外观（DIP 外形、SPDT 方块）

`<circuit>` 里可以加 `<appear>`，用 SVG 风格图元画外观，并把端口绑到内部 Pin：

```xml
<appear>
  <circ-port height="8" pin="200,290" width="8" x="-4" y="6"/>
  <rect fill="#ffffff" height="40" stroke="#000000" stroke-width="2"
        width="60" x="0" y="0"/>
  <circ-port height="8" pin="200,310" width="8" x="-4" y="26"/>
  <circ-port height="8" pin="200,500" width="8" x="26" y="-4"/>
  <circ-port height="10" pin="720,300" width="10" x="55" y="15"/>
  <rect height="2" stroke="#000000" width="8" x="0" y="9"/>
  <rect height="2" stroke="#000000" width="8" x="0" y="29"/>
  <rect height="2" stroke="#000000" width="8" x="52" y="19"/>
  <circ-anchor facing="east" height="6" width="6" x="27" y="17"/>
</appear>
```

| 元素 | 说明 |
|---|---|
| `<rect>` | `x y width height fill stroke stroke-width`（`fill="none"` 可空心） |
| `<line>` | `x1 y1 x2 y2 stroke stroke-width` |
| `<ellipse>` | `cx cy rx ry` |
| `<polyline>` / `<polygon>` | `points="x1,y1 x2,y2 …"` |
| `<path>` | SVG path `d` |
| `<text>` | `x y text`（**会跟着旋转，可能倒字**） |
| `<circ-port>` | `x y width height pin="内部Pin的x,y"` —— 端口位置 + 绑定的内部 Pin |
| `<circ-anchor>` | `x y facing` —— 外观的锚点，决定旋转中心 |

- **`pin` 必须和内部 Pin 的 `loc` 完全一致**，否则端口是死的。
- 端口坐标是**外观坐标系**（左上角 0,0），不是电路坐标。
- 方块里不要放 `<text>`：旋转 180° 会出现倒字。要文字就在父图用 `Text` 叠。
- 老版本（2.7.1）可能只显示默认方块，逻辑仍可用。

---

## 6. 常用元件名（本版实测）

`LibDump` 输出摘要：

| 库 | 工厂名 |
|---|---|
| Base | `Text`（还有 Poke/Edit/Select/Wiring/Menu Tool，仅工具） |
| Gates | `NOT Gate` `Buffer` `AND Gate` `OR Gate` `NAND Gate` `NOR Gate` `XOR Gate` `XNOR Gate` `Odd Parity` `Even Parity` `Controlled Buffer` `Controlled Inverter` |
| TTL | `7400` `7402` `7404` `7408` `7432` `7447` `7485` `7486` `Ttl74125` `74165` `74283` `747266` |
| Wiring | `Splitter` `Pin` `Probe` `Tunnel` `Pull Resistor` `Clock` `ProgrammableGenerator` `Constant` `Power` `Ground` `Transistor` `Transmission Gate` `Bit Extender` |
| Plexers | `Multiplexer` `Demultiplexer` `Decoder` `DisplayDecoder` `Priority Encoder` `BitSelector` |
| Arithmetic | `Adder` `Subtractor` `Multiplier` `Divider` `Negator` `Comparator` `Shifter` `BitAdder` `BitFinder` |
| Memory | `D Flip-Flop` `T Flip-Flop` `J-K Flip-Flop` `S-R Flip-Flop` `Register` `Counter` `Shift Register` `Random` `RAM` `ROM` `PlaRom` |
| I/O | `Button` `Switch` `DipSwitch` `Slider` `Joystick` `Keyboard` `Buzzer` `LED` `RGBLed` `Digital Oscilloscope` `7-Segment Display` `Hex Digit Display` `DotMatrix` `TTY` |

注意 **TTL 74125 的工厂名是 `Ttl74125`**（不是 `74125`）。

---

## 7. 加载失败的表现

`Loader.openLogisimFile()` 出错会弹 `JOptionPane`。headless 下变成：

```
Exception in thread "main" java.awt.HeadlessException
    at com.cburch.logisim.file.Loader.showError(Loader.java:430)
```

**看到 `HeadlessException` 就说明 `.circ` 本身有错**，不是环境问题。常见原因：

| 错误 | 触发 |
|---|---|
| `attribute value (001) is not valid` | `out` 写错 |
| `attribute value (40) is not valid` | `size` 只能是 20/30/50/70 |
| `attribute value (12) is not valid` | `inputs` 超范围 |
| `no such circuit` | `<main name>` 指向不存在的电路 |
| 找不到工厂 | `name` 拼错 / `lib` 编号对不上 |

反过来：**渲染成功 = 文件一定能加载**。所以 `CircExport` 也是最便宜的加载测试。

---

## 8. 版本差异（别把三个分支的例子混用）

| | 2.15 HUST（本 skill） | 2.7.1 官方经典 | Logisim-evolution |
|---|---|---|---|
| 顶层 source | `2.15.0.2.jar` / `.exe` | `2.7.1` | 更高版本号 |
| 输出 Pin | `<a name="output" val="true"/>` | 同左 | `<a name="type" val="output"/>` |
| 库编号 | 每份文件自定 | 每份文件自定 | 每份文件自定 |
| 文本元件 lib | 常见 `0`（Base） | 常见 `6`（Base） | `6` |
| `Hex Digit Display` | 无 `decimalPoint` 属性，两个输入脚 | 无 | 有 `decimalPoint`，DP 脚在 `loc+(20,0)` |
| CLI 真值表 | `-tty table` 实测空输出 | `-tty table` | `--tty table` |
| CLI 测试向量 | 无 | `-test` | `-w` |

三条实用结论：

1. **`lib` 号不要跨文件照抄**：同一个元件在不同工程里可能是 `lib="0"` 也可能是 `lib="6"`，
   永远读本文件的 `<lib desc="#Base" name="n">`。
2. 看到 `type="output"`、`decimalPoint`、`appearance="classic"` 这类属性，先怀疑是 evolution 例子；
   2.15 用 `FactoryDump` 查属性名，没有的不要写。
3. 本 skill 的 `pins/audit/sim/values` 是按 2.15 的 `getEnds()` 实测的；
   换版本先跑 `scripts/measure_geometry.py`，再用 `audit` 复核已有图。
