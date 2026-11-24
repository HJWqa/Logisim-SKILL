# 渲染与自检

---

## 1. 为什么不用 GUI 截图

- `SetForegroundWindow` 常被前台锁挡住，`PrintWindow` 只能抓窗口可见区（实测 1462×843），
  图会缺一截。
- 截图有仿真着色（绿/蓝），放进报告要另外转灰度，线宽也不对。
- 无头环境下 GUI 根本起不来。

**正确做法**：`CircExport`，走 Logisim「文件 → 导出图像」的同一段代码。

---

## 2. CircExport 做了什么

```java
Loader loader = new Loader(new Panel());
LogisimFile file = loader.openLogisimFile(new File(src));
Project proj = new Project(file);
Circuit circ = file.getCircuit(which);

// 量尺寸（需要 Graphics 做字体度量）
BufferedImage probe = new BufferedImage(8, 8, TYPE_INT_RGB);
Graphics pg = probe.getGraphics();
Bounds b = circ.getBounds(pg).expand(10);       // 内容包围盒 + 10 边距

BufferedImage img = new BufferedImage(w, h, TYPE_INT_RGB);
Graphics2D gg = (Graphics2D) g2.create();
gg.scale(scale, scale);
gg.translate(-b.getX(), -b.getY());

CircuitState state = proj.getCircuitState(circ);
proj.getSimulator().setCircuitState(state);
proj.getSimulator().step();                     // 传播一次，Power 驱动的 Pin 才显示 1

ComponentDrawContext ctx =
        new ComponentDrawContext(dummy, circ, state, g2, gg, true);  // true = 打印视图
circ.draw(ctx, null);
ImageIO.write(img, "png", target);
System.exit(0);                                 // 不退出的话 AWT 线程挂住 JVM
```

- `printerView = true`：导线/门体全黑，没有仿真着色。**Pin 组件仍按绿色画**（不是纯黑白）。
- `step()` 不能省：否则电源接的 Pin 显示 `?`/`E`。
- `scale` 建议 3～4（4 倍足够 A4 报告 14 cm 宽），自查用 2。
- 参数 `ALL` 会把每个电路导成 `<电路名>.png` 到目录里。

---

## 3. 命令

```bash
# skill CLI
python scripts/logisim.py render x.circ 电路名 out.png 4
python scripts/logisim.py render x.circ ALL outdir 2

# 直接调
%JAVA% -Djava.awt.headless=true -cp "%LOGISIM%;java\classes" ^
    CircExport x.circ 电路名 out.png 4
```

注意：

- PowerShell 里 `-Djava.awt.headless=true` 不会被自动拆开（要写成
  `"-Djava.awt.headless=true"` 或用参数数组）。
- **classpath 可以写 `.exe`**（launch4j 把 jar 附在 exe 尾部），不用解包。
- java 用绝对路径（裸 `java` 可能是 1.7 JRE）。

---

## 4. 自检：几何

`PinsDump` 把 Logisim 的 `Component.getEnds()` 全导成 TSV，Python 再做判定。
**不要自己按文档硬编码引脚坐标**——同一个元件在不同 `size`/`inputs` 下位置不同。

TSV 格式：

```
CIRC  <name> <bx> <by> <bw> <bh>
COMP  <factory> <idx> <x> <y> <bx> <by> <bw> <bh> <label>
ATTR  <compIdx> <name> <value>
END   <compIdx> <pinIdx> <x> <y> <IN|OUT|INOUT>
WIRE  <x1> <y1> <x2> <y2>
```

判定规则（`scripts/logisim.py audit`）：

| 检查 | 算法 | 等级 |
|---|---|---|
| 悬空端点 | 端点不在引脚上、出现次数 <2、也不落在他线内部 | ERROR |
| 未接引脚 | 引脚不在任何导线端点上、也不在任何导线内部 | ERROR |
| 同向重叠 | 共线（同 x 或同 y）且投影有交叠 | ERROR |
| 穿元件体 | 线段与该元件外接矩形（内缩 2）有交，且端点不是该元件引脚 | ERROR |
| 文字压线 | Text 外接矩形（内缩 3）被导线穿过 | ERROR |
| 电源短路 | 同一网络（DSU 连通分量）上同时有 `Power` 和 `Ground` | ERROR（必是 E） |
| 多驱动 | 同一网络上 ≥2 个 `OUT` 脚（`Power`/`Ground` 除外） | WARN（值冲突才变红） |
| 文字重叠 | 两个 Text 外接矩形相交（内缩 2） | WARN |
| 元件同坐标 | 多个元件 `loc` 相同（`DipSwitch` 压 `SPDT_SEL` 的 S 脚除外） | WARN |
| 交叉点 | 只统计个数 | INFO（`--cross-gap N` 才把“离结点 <N”列为风格提示） |
| 结点数 | 度数 ≥3 的点（端点/引脚/线内三者合计） | INFO |

### 4.1 为什么用“度数”判结点

Logisim 只在 **3 条以上连在一起**的位置画实心圆点。两根线端点相接（拐角）不画点。
所以：

```python
deg = 以 p 为端点的导线数 + 以 p 为端点的引脚数 + 穿过 p 的导线数（不含端点在 p 的）
结点 = deg >= 3
```

### 4.2 常见误报及处理

| 现象 | 原因 | 处理 |
|---|---|---|
| LED 被报“穿元件体” | LED 的 `bounds` 包含标签，导线接在 `loc` 上，而 `loc` 在 bounds 内 | 已按“端点即该元件引脚”排除 |
| Text 被报“压线” | `valign=base`，文字矩形底边正好在导线上 | 用内缩 3 判定，贴边不算 |
| DipSwitch / SPDT_SEL 报“未接引脚” | 两个元件引脚**同坐标直接压在一起**（Switch 脚压在 `S` 上），中间没导线 | 同坐标 ≥2 个引脚算已连（Logisim 也这么认） |
| 电源装饰脚 `U1-14` 等 | 纯文字 Pin，不参与逻辑 | 不参与真值表，审计里仍要求有线 |

### 4.3 测不到的项目

以下问题这套工具**测不出来**，要人看图：

- 标签是否被别的东西挡住/文字重叠
- 交叉点是否在视觉上压在门名上
- 整体版面是否平衡（大片空白 / 拥挤）
- 引脚号数字是否指对了端子（数字是纯 Text，工具不知道含义）

另有两条静态分析的边界：

- `Tunnel` 靠**同名**连接，几何上不相连 → 不进入网络（DSU）分析，
  所以两个同名 Tunnel 上各接一个驱动器，`多驱动` 查不出来；靠 `values` 跑仿真才准。
- `多驱动` 只数“输出脚个数”。Logisim 会把**同值**的多个驱动合并成该值，
  所以它是 WARN，不是 ERROR；`电源短路` 才是必然的 E。

---

## 5. 自检：真值表

`SimTable` 直接驱动 Logisim 的 Propagator，比自己写求值器可靠得多
（不用处理多驱动 `E`、三态、子电路、位宽）。

```bash
python scripts/logisim.py sim x.circ 表决器_74LS00
```

输出：

```
drivers(DipSwitch): (290,240) (290,360) (290,480)  probes: L LED(1220,520)
000 -> 1
100 -> 1
…
```

要点：

1. **驱动源自动选**：先找 1 位 `DipSwitch`（按 y 从上到下 = A、B、C）；
   一个都没有时退化用输入 `Pin`（排除 `U1-14` 这种电源装饰脚）。
2. **探测点**：不指定就取所有 `LED` + 输出 `Pin`；要给就用 `x,y` 列表。
3. **必须用同步传播**：`state.getPropagator().propagate()`，
   不要启动 `Simulator` 线程再改值——会偶发 `Propagator` NPE。
4. 改 `DipSwitch` 状态要反射改私有字段 `vals`；改 `Pin` 改 `value`：

```java
Object data = state.getInstanceState(c).getData();
Field f = data.getClass().getDeclaredField("vals");   // Pin 用 "value"
f.setAccessible(true);
Value[] vals = (Value[]) f.get(data);
vals[0] = Value.createKnown(BitWidth.create(1), bit);
state.markComponentAsDirty(c);
state.getPropagator().propagate();
```

5. **读表方向**：`SPDT_SEL` 里 `S=0 → C=T1=+5V=1`，
   所以 `DipSwitch` 原始值 `0` = 扳手朝上 = **逻辑 1**。
   `sim` 打印的是原始值，换算时别读反（或干脆把期望表按原始值写）。

### 5.1 时序：`--clock` / `--ticks`

组合表只枚举输入组合，不会自动打拍。时序电路用：

```bash
python scripts/logisim.py sim 计数器.circ 计数器 500,300 --clock CLK --ticks 8
```

实现（`SimTable`）：

```java
// 每个上升沿：低 → 传播 → 高 → 传播 → 采样 → 低 → 传播
setClock(0); propagate();
for (int t = 1; t <= ticks; t++) {
    setClock(1); propagate();      // 上升沿，寄存器在这里锁存
    setClock(0); propagate();
    print("t" + t + " -> " + read(probes));
}
```

- 采样点在**上升沿之后**，对 `trigger=rising` 的 DFF/Register/Counter 正好。
- `--combo` 固定其余 1 位输入（顺序同上：从上到下）。
- 时钟只能是 `Pin` 或 `DipSwitch`；`Clock` 元件由仿真线程驱动，命令会拒绝。
- 多位 `DipSwitch` 不参与驱动（`vals[0]` 只对应第 1 位）。

---

## 6. 导线变红（E）怎么查

Logisim 的导线配色 = 当前电平：

| 颜色 | 值 | 含义 |
|---|---|---|
| 亮绿 | 1 | 高电平 |
| 深绿 | 0 | 低电平 |
| 蓝 | x | 未驱动/高阻 |
| **红** | **E** | **冲突：同一网络有多个互相打架的驱动** |

红色几乎只有三种来源：

1. **同一网络上两个驱动**：两个输出 Pin、两个门输出、Power 和 Ground 接在一起、
   输入 Pin 又接了开关。
2. **Poke 工具点到导线上**：Logisim 允许戳导线临时给值，与已有驱动冲突就是 E。
   （最容易误判成“文件坏了”，其实只是 GUI 运行时状态。）
3. **子电路内部有错**：子电路的输出 Pin 会把 E 传到父图。

诊断命令（不用看 GUI）：

```bash
python scripts/logisim.py values x.circ 电路名 --red
# 或看全部、指定开关组合
python scripts/logisim.py values x.circ 电路名 010
```

- `combo` 的每一位对应一个 1 位 `DipSwitch`，**从左到右 = 从上到下**，
  和 `sim` 打印的位串完全同一套顺序。
- 0/1 是**器件原始值**：`0 = 扳手朝上 = 逻辑 1`（因为 `SPDT_SEL` 里 `S=0 → T1=+5V`）。
  所以 `values ... 010` 与 `sim` 表里 `010 -> …` 那一行必须一致——不一致就是工具错。

输出会逐根导线打印两端坐标和值，`<<< E` 就是红的那根，最后一行给出
`绿(1)=… 深绿(0)=… 蓝(x)=… 红(E)=…` 统计。

**如果命令行显示 `红(E)=0`，但 GUI 里是红的**，那就是运行时状态：

- 按 `Ctrl+R`（Simulation → Reset Simulation）清掉戳出来的强制值；
- 或用 Poke/箭头工具再点一下那根线取消；
- 关闭文件重开（有未保存改动会提示）。

**如果命令行也报红**，就是真的有冲突：按上面三种来源逐个删掉多余的驱动。
最常见的是“输入 Pin 和开关/电源接在同一个网上”——删掉 Pin，或改成输出 Pin 当测试点。

---

## 7. 一次完整的验证输出应该长什么样

```
### 表决器_74LS00   元件 58  导线 45  引脚 36
  [OK  ] 悬空端点       0
  [OK  ] 未接引脚       0
  [OK  ] 同向重叠       0
  [OK  ] 穿元件体       0
  [OK  ] 文字压线       0
  [OK  ] 电源短路       0  []
  [OK  ] 多驱动        0
  [OK  ] 文字重叠       0
  [OK  ] 元件同坐标      0
  [OK  ] 交叉点        4  [(440, 330), (420, 490), (180, 490), (180, 370)]
```

```
drivers(DipSwitch): (290,240) (290,360) (290,480)  probes: L LED(1220,520)
000 -> 1     ← A=B=C=1 → L=1
110 -> 0     ← C=1 单独 → L=0
```

交叉点默认只报个数（`INFO`）。Logisim 的圆点是明确的连接标记，
**交叉离圆点多近都不影响判读**；想要更疏的版式才用 `--cross-gap 40` 看提示。
