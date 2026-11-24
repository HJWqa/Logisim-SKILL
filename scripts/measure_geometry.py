# -*- coding: utf-8 -*-
"""一次性量出 Logisim 2.15（HUST 版）常用元件的引脚几何，输出 markdown 表。

跑法（在 skill 目录下）：
    python measure_geometry.py > ../../references/02_geometry.md
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from logisim import Env, load_tsv  # noqa: E402

HEAD = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
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
  <main name="probe"/>
  <options>
    <a name="gateUndefined" val="ignore"/>
    <a name="simlimit" val="1000"/>
    <a name="simrand" val="0"/>
  </options>
  <mappings/>
  <toolbar/>
  <circuit name="probe">
"""
TAIL = """  </circuit>
</project>
"""


def run(env, comps):
    xml = HEAD + "\n".join(comps) + "\n" + TAIL
    fd, path = tempfile.mkstemp(suffix=".circ")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    fd, tsv = tempfile.mkstemp(suffix=".tsv")
    os.close(fd)
    try:
        r = env.run("PinsDump", path, tsv)
        if r.returncode != 0:
            return None
        return load_tsv(tsv)["probe"]
    finally:
        os.unlink(path)
        os.unlink(tsv)


def comp(lib, name, x, y, attrs=None):
    a = "".join('\n      <a name="%s" val="%s"/>' % kv for kv in (attrs or {}).items())
    if a:
        return '    <comp lib="%d" loc="(%d,%d)" name="%s">%s\n    </comp>' % (
            lib, x, y, name, a)
    return '    <comp lib="%d" loc="(%d,%d)" name="%s"/>' % (lib, x, y, name)


def describe(c, idx):
    comp0 = [z for z in c["comps"] if z["idx"] == idx][0]
    pins = sorted([e for e in c["ends"] if e["comp"] == idx], key=lambda e: e["pin"])
    offs = [(e["x"] - comp0["x"], e["y"] - comp0["y"], e["dir"]) for e in pins]
    b = comp0["bounds"]
    rel = (b[0] - comp0["x"], b[1] - comp0["y"], b[2], b[3])
    return offs, rel


def fmt(offs):
    return " ".join("%s%+d,%+d" % ("I" if d == "IN" else "O" if d == "OUT" else "B",
                                    x, y) for x, y, d in offs)


def main():
    env = Env()
    print("# 元件几何实测表（Logisim 2.15 HUST 版）\n")
    print("> 全部由 `PinsDump` 从 Logisim 自身读出来的 `Component.getEnds()` 得到，**不是猜的**。")
    print("> 坐标系：`loc` 是元件锚点，偏移是 `引脚 − loc`，y 轴向下。")
    print("> 自己画新元件前，先跑 `python scripts/logisim.py pins x.circ` 复核，")
    print("> 换 Logisim 版本时代码可能不同。\n")
    print("图例：`I` 输入脚、`O` 输出脚、`B` 双向。\n")

    # ---- 门 ----
    print("## 1. 门（`#Gates`, lib=1）\n")
    print("`size` 决定门体大小，**输入脚的 x 偏移随 gate 外形不同**：\n")
    print("| 门 | size=20 | size=30 | size=50 |")
    print("|---|---|---|---|")
    rows = {}
    for g in ["AND Gate", "OR Gate", "NAND Gate", "NOR Gate", "XOR Gate",
              "XNOR Gate", "NOT Gate", "Buffer"]:
        cells = []
        for sz in (20, 30, 50):
            x = 300
            body = [comp(1, g, x, 300, {"size": sz, "inputs": 2})
                    if g not in ("NOT Gate", "Buffer")
                    else comp(1, g, x, 300, {"size": sz})]
            c = run(env, body)
            if c is None or not c["comps"]:
                cells.append("不支持")
                continue
            offs, rel = describe(c, 0)
            lead = min(o[0] for o in offs)
            cells.append("输入 x%+d，门体 %dx%d" % (lead, rel[2], rel[3]))
        rows[g] = cells
        print("| %s | %s |" % (g, " | ".join(cells)))

    print("\n### 多输入时 y 的分布（size=30）\n")
    print("| 门 | inputs=2 | 3 | 4 | 5 | 6 | 8 |")
    print("|---|---|---|---|---|---|---|")
    for g in ["AND Gate", "NAND Gate"]:
        cells = []
        for n in (2, 3, 4, 5, 6, 8):
            c = run(env, [comp(1, g, 300, 300, {"size": 30, "inputs": n})])
            offs, _ = describe(c, 0)
            dys = [o[1] for o in offs if o[2] == "IN"]
            cells.append(", ".join("%+d" % d for d in dys))
        print("| %s | %s |" % (g, " | ".join(cells)))

    print("\n**关键**：`size=30` 时 AND/OR 输入在 `x−30`，而 NAND/NOR/XOR 在 `x−40`，")
    print("XNOR 在 `x−50`。写成同一个数会短线 10～20 格，且常被文字标签挡住看不出来。")
    print("输入数 ≥3 时**没有 y=0 的那个脚**，y 是对称地分布在 0 两侧。\n")
    print("`out` 属性恒为 `\"01\"`，与输入个数无关；写 `\"001\"` 会报")
    print("`attribute value (001) is not valid` 并在 headless 下变成 `HeadlessException`。\n")

    # ---- 连线类 ----
    print("## 2. 导线类（`#Wiring`, lib=3）\n")
    print("| 元件 | 引脚 | 外接矩形（相对 loc） | 备注 |")
    print("|---|---|---|---|")
    cases = [
        ("Pin", {"facing": "east", "output": "false", "label": "A"}, "输入脚；方框向左"),
        ("Pin", {"facing": "west", "output": "true", "label": "Y"}, "输出脚；方框向右"),
        ("Pin", {"facing": "north", "output": "false", "label": "A"}, "竖放"),
        ("Pin", {"facing": "east", "output": "false", "width": "4", "label": "D"},
         "4 位输入：右边多一个值框"),
        ("Tunnel", {"facing": "east", "label": "n1"}, "同名相连"),
        ("Probe", {"facing": "east"}, "显示值"),
        ("Power", {"facing": "north"}, "只有 +5V 语义"),
        ("Ground", {"facing": "south"}, "只有 0 语义"),
        ("Pull Resistor", {"facing": "south", "pull": "0"}, "单脚；facing=south 体向上"),
        ("Pull Resistor", {"facing": "north", "pull": "1"}, "facing=north 体向下"),
        ("Clock", {"facing": "east"}, "输出方波"),
        ("Constant", {"facing": "east", "value": "1"}, "恒定电平"),
    ]
    for name, attrs, note in cases:
        c = run(env, [comp(3, name, 300, 300, attrs)])
        offs, rel = describe(c, 0)
        rect = "(%+d,%+d) %dx%d" % rel
        print("| %s | `%s` | %s | %s |" % (name, fmt(offs), rect, note))

    print("\n- `Pin` 朝东时**连接点就是 loc**，方框朝左；朝西时仍在 loc，方框朝右。")
    print("  所以左边放输入脚用 `facing=east`，右边放输出脚用 `facing=west`。")
    print("- **输入 Pin 是驱动器**：同一网络上不能再接开关/电源，否则多驱动变成 `E`。")
    print("- **输出 Pin 是接收器**：可以挂在 Power/Ground 上看 1/0，不会冲突。")
    print("- `Pull Resistor` 只有一个脚，含义是“把本节点弱拉到 0/1”，不是两端电阻。")
    print("- `Tunnel` 靠**同名**相连，跨电路不受几何限制；但旗子会盖线，别拿它当电源符号。\n")

    # ---- I/O ----
    print("## 3. 交互元件（`#I/O`, lib=7）\n")
    print("| 元件 | 引脚 | 外接矩形（相对 loc） | 说明 |")
    print("|---|---|---|---|")
    cases = [
        ("Switch", {"facing": "east"}, "SPST：左 IN 右 OUT，运行时状态"),
        ("Switch", {"facing": "south"}, "竖放"),
        ("DipSwitch", {"facing": "east", "NSwitches": "1"}, "1 位拨动；脚在 loc 下方 10"),
        ("DipSwitch", {"facing": "south", "NSwitches": "1"}, "竖放；脚在 loc 右侧 10"),
        ("DipSwitch", {"facing": "south", "NSwitches": "3"}, "3 位；每 20 一格"),
        ("Button", {"facing": "east"}, "按时为 1"),
        ("LED", {"facing": "west"}, "单脚；另一端元件内部接地"),
        ("LED", {"facing": "east"}, "体在 loc 左侧"),
    ]
    for name, attrs, note in cases:
        c = run(env, [comp(7, name, 300, 300, attrs)])
        offs, rel = describe(c, 0)
        print("| %s | `%s` | %s | %s |" % (name, fmt(offs), "(%+d,%+d) %dx%d" % rel, note))

    print("\n- `Switch` 是**通/断**型：接 +5 V 后断开就是悬空，不能直接当 0/1 源。")
    print("  要手点出 0/1 用 `DipSwitch`，或自己做 SPDT 子电路。")
    print("- `DipSwitch` 的**“关”位在离引脚最远的一端**：朝南放时 0 = 滑块在上。")
    print("- `LED` 只有一个连接点，另一端在元件内部接地；实物要串 470 Ω。\n")

    # ---- 多路选择器 ----
    print("## 4. 常用功能块\n")
    print("| 元件 | lib | 引脚 | 矩形 |")
    print("|---|---|---|---|")
    cases = [
        (4, "Multiplexer", {"facing": "east", "select": "1", "width": "1"}),
        (4, "Multiplexer", {"facing": "east", "select": "2", "width": "1"}),
        (4, "Decoder", {"facing": "east", "select": "2"}),
        (3, "Splitter", {"fanout": "2", "incoming": "2", "bit0": "1", "bit1": "2"}),
        (3, "Splitter", {"fanout": "4", "incoming": "4", "bit0": "1", "bit1": "2",
                          "bit2": "3", "bit3": "4"}),
        (5, "Adder", {"facing": "east", "width": "4"}),
        (5, "Subtractor", {"facing": "east", "width": "4"}),
        (5, "Comparator", {"facing": "east", "width": "4"}),
        (6, "D Flip-Flop", {"facing": "east", "width": "1"}),
        (6, "Register", {"facing": "east", "width": "4"}),
        (6, "Counter", {"facing": "east", "width": "4"}),
        (6, "RAM", {"facing": "east", "addrWidth": "2", "dataWidth": "4"}),
        (6, "ROM", {"facing": "east", "addrWidth": "2", "dataWidth": "4"}),
        (7, "Hex Digit Display", {"facing": "east"}),
        (7, "7-Segment Display", {"facing": "east"}),
    ]
    for lib, name, attrs in cases:
        c = run(env, [comp(lib, name, 400, 300, attrs)])
        if c is None or not c["comps"]:
            print("| %s | %d | 不支持 | — |" % (name, lib))
            continue
        offs, rel = describe(c, 0)
        print("| %s | %d | `%s` | (%+d,%+d) %dx%d |" % (
            name, lib, fmt(offs), rel[0], rel[1], rel[2], rel[3]))

    print("\n`Multiplexer` 的 `select` 脚在左下（`selloc=bl`），第 0 路输入在最上面。")
    print("做 2 选 1 开关时 `select=1, width=1` 正好四边各一脚，最好接线。\n")

    # ---- TTL ----
    print("## 5. TTL 整片元件（lib=2）\n")
    print("| 元件 | 引脚数 | 矩形 | 备注 |")
    print("|---|---|---|---|")
    for name in ["7400", "7402", "7404", "7408", "7432", "7486", "74125"]:
        c = run(env, [comp(2, name, 400, 300)])
        if c is None or not c["comps"]:
            print("| %s | — | — | 加载失败 |" % name)
            continue
        offs, rel = describe(c, 0)
        print("| %s | %d | (%+d,%+d) %dx%d | `getEnds()` 顺序，**不是 DIP 引脚号** |"
              % (name, len(offs), rel[0], rel[1], rel[2], rel[3]))
    print("\n**不要用 TTL 整片元件画引脚级图**：它有 DIP 外形，但不标引脚号，")
    print("`getEnds()` 的顺序也和真实 DIP 顺序不同（7400 是 1A/1B/1Y/2A/2B/2Y/GND/VCC/…）。")
    print("引脚级连接图请用手画的门 + 端子数字，或另做带引脚号的 DIP 外形子电路。\n")

    # ---- 位宽 / 总线 ----
    print("## 6. 位宽与总线（多位数）\n")
    print("| 元件 | 属性（`FactoryDump` 实测） | 说明 |")
    print("|---|---|---|")
    print("| `Pin` | `width` | `width=N` 时连接点仍是 `loc`，右边多出 N 个格的值框 |")
    print("| `Splitter` | `fanout` `incoming` `bit0..bitN` | `incoming`=输入总线宽度，"
          "`fanout`=分出的线数；第 i 根接 `bit{i}` 指定的位 |")
    print("| `Bit Extender` | `in_width` `out_width` `type` | `type` = zero/sign/one |")
    print("| `Adder` / `Subtractor` | `width` | 进位/借位脚在 `loc` 的左下 |")
    print("| `Comparator` | `width` `mode` | `mode` = twosComplement/unsigned |")
    print("| `Register` | `width` `trigger` `Select` | `Select` = low/high（使能极性） |")
    print("| `Counter` | `width` `max` `ongoal` `trigger` `behavior` | `ongoal` = wrap/stay/… |")
    print("| `RAM` / `ROM` | `addrWidth` `dataWidth` `bus` `Select` | `bus` = combined/separate |")
    print("\n要点：\n")
    print("1. **2.15 的 `Splitter` 不支持多位数扇出**：`bit0=\"1,2\"` 这种写法会加载失败；")
    print("   一位一根，`fanout=4, incoming=4, bit0..bit3 = 1..4`。")
    print("2. 多位 `Pin` 的**值框**占几十格宽，相邻 Pin 纵向间距按 ≥60 留，否则框叠框。")
    print("3. `Hex Digit Display` 有**两个输入脚**（`loc` 与 `loc+10,0`），第二位不是数据位；")
    print("   4 位总线横穿过去会被当成接上。")
    print("4. 功能块（Register/Counter/RAM…）的 `getEnds()` 顺序**不等于引脚名顺序**；")
    print("   画图前用 `logisim.py pins` 看坐标，接完先 `sim` 或 `values` 验证，别按记忆连。")
    print("5. 2.15 HUST 版**没有** `decimalPoint` 这类 evolution 专有属性；")
    print("   从 Logisim-evolution 的示例抄属性会加载失败，以 `FactoryDump` 输出为准。\n")


if __name__ == "__main__":
    main()
