# 踩坑速查：症状 → 原因 → 修法

> 按“你看到什么”排序。带 ⚠ 的是已经踩过两次以上的。

---

## 打开 / 加载

| 症状 | 原因 | 修法 |
|---|---|---|
| ⚠ `HeadlessException` + `Loader.showError` | **`.circ` 本身有错**，Logisim 想弹窗但无头 | 看 §属性，常见是 `out`/`size`/`inputs` 非法；用 GUI 打开看弹窗原文 |
| `attribute value (001) is not valid` | `out` 属性写成 `"001"` | 恒写 `out="01"` |
| `attribute value (40) is not valid` | 门 `size=40` | `size` 只能 20/30/50/70（20 只给 NOT/Buffer） |
| `attribute value (11) is not valid` | `inputs=11` | 输入数 2..10 |
| 加载失败，提示属性名不认识 | 抄了 evolution 的 `decimalPoint` / `type="output"` | 2.15 没有这些属性；用 `FactoryDump` 查本版属性名 |
| `Splitter` 加载失败 | `bit0="1,2"` 一次给多位（evolution 写法） | 2.15 一位一根：`fanout=4 incoming=4 bit0..3=1..4` |
| 打不开、无提示 | java 是 1.7 | 用绝对路径的 java 11+ |
| GUI 里打开是空白页 | `<main name>` 指向不存在的电路 | 改成实际电路名 |
| 改了 `.circ` 后 diff 炸开 | 用 GUI 保存了手写文件 | 手写文件别用 GUI 保存；先备份 |

## 连线 / 仿真

| 症状 | 原因 | 修法 |
|---|---|---|
| 线看起来接上了，仿真没信号 | 坐标差 10 格；被标签挡住看不出来 | `logisim.py pins` 量真实引脚坐标 |
| ⚠ 门输入线短 10 格 | 按 `x−40` 写了 AND/OR（实际 `x−30`）或按 `x−30` 写了 NAND | 见 SKILL §6 的表；或 `pins` 实测 |
| 引脚显示 `E`（红） | 同一个网络上有两个驱动器 | `logisim.py values x.circ 电路名 --red` 找出是哪几根；输入 Pin 不能再接开关/电源 |
| ⚠ 整张图有几根线突然变红，文件没动过 | **Poke 工具戳过导线**（Logisim 允许临时给值，与驱动冲突就是 E） | `Ctrl+R` 复位仿真；或再点一下取消。命令行 `values` 显示 `红(E)=0` 即可放心 |
| 一大片线都变红 | `Power` 和 `Ground` 接到同一个网络 | `audit` 的 `电源短路` 会直接点名；删掉其中一根 |
| 4 位总线显示 `UUUU` / `EEEE` | 总线被 1 位脚短路（最常见：`Hex Digit Display` 的第二个脚 `loc+(10,0)`） | 让总线绕开那个脚，或改用 `Splitter` 单独引出来 |
| 多位 Pin 的值框跟隔壁叠住 | 多位 Pin 的框比 1 位宽几十格 | 纵向间距 ≥60；`audit` 的 `文字重叠` 查不到值框 |
| 引脚显示 `x`（蓝） | 高阻/未驱动 | 检查是否有确定电平；`Pin(tristate=true)` 改成 `false` |
| 输出一直是 1/0 不变 | 输入 Pin 从来没被驱动（无头下 Pin 没有初始值） | 用 `DipSwitch` 或 `Power`/`Ground` 给固定电平 |
| 子电路输出报 `E` | 两个传输门输出并联（SPDT 旧做法） | 改用 2 选 1 `Multiplexer` |
| 点 `S` 引脚没反应 | 子电路本身点不动；`S` 上没有扳手 | 在 `S` 上放 1 位 `DipSwitch`（输出脚对准 `S`） |
| 扳手方向反了 | 扳手放在下方朝北 | 放方块**上方、朝南** |
| 扳手点不到 | 子电路白底盖住了它 | 文件里先写子电路 `<comp>`，再写扳手 |

## 版面 / 出图

| 症状 | 原因 | 修法 |
|---|---|---|
| 交叉离圆点很近（≤12 格） | 风格偏好，**不是错误**；圆点才是连接标记 | 默认不提示；介意就挪开（`--cross-gap 40` 可开提示） |
| 圆点旁边多出一截短线 | 旧走线残留（改了坐标没删旧 `wire`） | 删掉；审计报“悬空端点” |
| 导线穿过门体 | 走线抄了近路 | 绕开；审计报“穿元件体” |
| 文字被线穿过 | Text 放在线上了 | 移开 20～40；审计报“文字压线” |
| 两段线看着一根、点选只中一段 | 同向重叠 | 合并成一根；审计报“同向重叠” |
| 位号压在门形里 | 用了门的 `label` 属性 | 改用单独 `Text` 放门上方 |
| 打开后顶栏没有工具 | `<toolbar/>` 空 | 按 SKILL §5 填满；`ToolbarDump` 验证 |
| 元件贴着画布左上角，选不中 | 坐标从 (0,0) 开始 | 全部坐标 `+200,+140` |
| PNG 少一截 | 用了 GUI 截图（`PrintWindow` 只抓可见区） | 改用 `CircExport` |
| PNG 有灰边/彩边 | PNG 有仿真着色或画布边 | `printerView=true`；导出前 `step()` 一次 |
| 电源脚显示 `?` | 导出前没传播 | `proj.getSimulator().step()` |
| 中文变方框 | 担心字体 | `Dialog plain` 会做字体回退，实测正常 |
| 打印出来线太细/太小 | scale 不够 | 4 倍起步 |
| 交叉/线在报告里变成灰色 | 用了仿真视图 | 打印视图（printerView） |

## 脚本 / 环境

| 症状 | 原因 | 修法 |
|---|---|---|
| 报“找不到或无法加载主类”，无其他提示 | 裸 `java` 解析到 1.7 JRE | 用绝对路径 `…\zulu-11\bin\java.exe` |
| `java` 命令参数被吞 | PowerShell 把 `-Djava.awt.headless=true` 拆开 | 写成 `"-Djava.awt.headless=true"` |
| `javac` 找不到 | 只装了 JRE | 装 JDK，或改 `-cp` 用已编译的 `classes/` |
| 脚本跑完 JVM 不退出 | AWT 线程非守护 | 显式 `System.exit(0)` |
| 改了几何表后对不上 | 换了 Logisim 版本 | 重跑 `scripts/measure_geometry.py` |

---

## 一句话记住

1. **几何不要猜，`pins` 量。**
2. **`out` 恒 `"01"`，`size` 只能 20/30/50/70。**
3. **有圆点才是连；交叉多远都不影响判读。**
4. **`HeadlessException` = 文件有错。**
5. **手写 `.circ` 不要过 GUI 保存。**
