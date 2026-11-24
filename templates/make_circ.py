# -*- coding: utf-8 -*-
"""生成 .circ 的最小骨架（可以直接改）。

用法：
    1. 复制本文件到你的工作目录；
    2. 改 OUT 和电路内容；
    3. `python make_circ.py` 生成 .circ；
    4. `python <skill>/scripts/logisim.py audit out.circ`
    5. `python <skill>/scripts/logisim.py sim out.circ 电路名`
    6. `python <skill>/scripts/logisim.py render out.circ 电路名 out.png 4`

设计要点：
- 所有坐标先按"局部坐标"写，导出时统一加 (OX, OY)，电路不会贴画布左上角；
- 元件函数只写**必须显式给**的属性，其余用 Logisim 默认值；
- 引脚坐标不要在这里硬编码 —— 用 `logisim.py pins` 从 Logisim 实测。
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "新建电路.circ")
MAIN = "主电路"

FONT = "Dialog plain 16"
FONT_SMALL = "Dialog plain 14"
FONT_TINY = "Dialog plain 12"

# 画布留白：所有坐标统一加这个偏移
OX, OY = 200, 140

# 门输入脚的实测几何（size=30，朝东，loc=输出）
#   AND/OR            输入 x-30
#   NAND/NOR/XOR      输入 x-40
#   XNOR              输入 x-50
GATE_LEAD = {
    "AND Gate": 30, "OR Gate": 30,
    "NAND Gate": 40, "NOR Gate": 40, "XOR Gate": 40, "XNOR Gate": 50,
}


def _a(name, val):
    return '      <a name="%s" val="%s"/>' % (name, val)


def _tool(lib, name, attrs=None):
    if not attrs:
        return '    <tool lib="%d" name="%s"/>' % (lib, name)
    return '    <tool lib="%d" name="%s">\n%s\n    </tool>' % (
        lib, name, "\n".join(attrs))


def toolbar():
    """打开文件就有能用的工具，不用去左侧库里翻。lib 编号必须和 xml() 一致。"""
    pin_in = [_a("facing", "east"), _a("output", "false"), _a("width", "1"),
              _a("tristate", "false"), _a("pull", "none"), _a("label", ""),
              _a("labelloc", "north"), _a("labelfont", FONT), _a("labelcolor", "#000000")]
    pin_out = [_a("facing", "west"), _a("output", "true"), _a("width", "1"),
               _a("tristate", "false"), _a("pull", "none"), _a("label", ""),
               _a("labelloc", "north"), _a("labelfont", FONT), _a("labelcolor", "#000000")]
    gate = [_a("facing", "east"), _a("width", "1"), _a("size", "30"),
            _a("inputs", "2"), _a("out", "01"), _a("label", ""),
            _a("labelfont", FONT), _a("labelcolor", "#000000"),
            _a("negate0", "false"), _a("negate1", "false")]
    switch = [_a("facing", "east"), _a("width", "1"), _a("color", "#ffffff"),
              _a("label", ""), _a("labelloc", "north"),
              _a("labelfont", FONT), _a("labelcolor", "#000000")]
    led = [_a("facing", "west"), _a("color", "#f00000"), _a("offcolor", "#404040"),
           _a("active", "true"), _a("label", ""), _a("labelloc", "north"),
           _a("labelfont", FONT), _a("labelcolor", "#000000")]
    text = [_a("text", ""), _a("font", FONT), _a("color", "#000000"),
            _a("halign", "center"), _a("valign", "base")]
    return "\n".join([
        "  <toolbar>",
        _tool(0, "Poke Tool"),
        _tool(0, "Edit Tool"),
        "    <sep/>",
        _tool(0, "Text Tool", text),
        _tool(3, "Pin", pin_in),
        _tool(3, "Pin", pin_out),
        "    <sep/>",
        _tool(1, "NAND Gate", gate),
        _tool(1, "XOR Gate", gate),
        "    <sep/>",
        _tool(3, "Power", [_a("facing", "north")]),
        _tool(3, "Ground", [_a("facing", "south")]),
        _tool(3, "Pull Resistor", [_a("facing", "north"), _a("pull", "0")]),
        _tool(7, "Switch", switch),
        _tool(7, "LED", led),
        "  </toolbar>",
    ])


class Circuit:
    def __init__(self, name):
        self.name = name
        self.parts = []
        self.wires = []
        self.pins = {}      # label -> (x, y, is_output)
        self.gates = []     # (factory, [input points], output point)

    # ---------- 元件 ----------
    def comp(self, lib, x, y, name, attrs):
        self.parts.append('    <comp lib="%d" loc="(%d,%d)" name="%s">\n%s\n    </comp>'
                          % (lib, x + OX, y + OY, name,
                             "\n".join(_a(k, v) for k, v in attrs)))

    def gate(self, name, x, y, inputs=2, size=30):
        """放一个门，返回 (输入点列表, 输出点)。坐标是局部坐标（未加 OX/OY）。"""
        lead = GATE_LEAD[name] + (size - 30)      # size 变大，输入更靠左
        attr = [("facing", "east"), ("width", "1"), ("size", str(size)),
                ("inputs", str(inputs)), ("out", "01"), ("label", ""),
                ("labelfont", FONT), ("labelcolor", "#000000")]
        attr += [("negate%d" % i, "false") for i in range(inputs)]
        self.comp(1, x, y, name, attr)

        # 输入脚 y 分布：n=2 时 ±10；n>=3 时步长 10，不经过 0
        if inputs == 2:
            dys = [-10, 10]
        else:
            dys = [10 * (i - (inputs - 1) / 2) for i in range(inputs)]
            dys = [int(round(d)) for d in dys]
        ins = [(x - lead, y + d) for d in dys]
        out = (x, y)
        self.gates.append((name, ins, out))
        return ins, out

    def pin(self, label, x, y, output=False):
        self.comp(3, x, y, "Pin", [
            ("facing", "west" if output else "east"),
            ("output", "true" if output else "false"),
            ("width", "1"), ("tristate", "false"), ("pull", "none"),
            ("label", label), ("labelloc", "north"),
            ("labelfont", FONT), ("labelcolor", "#000000")])
        self.pins[label] = (x, y, output)
        return (x, y)

    def text(self, x, y, s, font=FONT, halign="center"):
        self.comp(0, x, y, "Text", [
            ("text", s), ("font", font), ("color", "#000000"),
            ("halign", halign), ("valign", "base")])

    def power(self, x, y, facing="north"):
        self.comp(3, x, y, "Power", [("facing", facing)])

    def ground(self, x, y, facing="south"):
        self.comp(3, x, y, "Ground", [("facing", facing)])

    def led(self, label, x, y, facing="west"):
        self.comp(7, x, y, "LED", [
            ("facing", facing), ("color", "#f00000"), ("offcolor", "#404040"),
            ("active", "true"), ("label", label), ("labelloc", "north"),
            ("labelfont", FONT), ("labelcolor", "#000000")])

    def dip(self, x, y, facing="south", n=1):
        self.comp(7, x, y, "DipSwitch", [
            ("facing", facing), ("NSwitches", str(n)), ("color", "#ffffff"),
            ("label", ""), ("labelloc", "north"),
            ("labelfont", FONT), ("labelcolor", "#000000")])

    def pull(self, x, y, value=0, facing="north"):
        self.comp(3, x, y, "Pull Resistor",
                  [("facing", facing), ("pull", str(value))])

    # ---------- 导线 ----------
    def w(self, *pts):
        """折线：w((x1,y1),(x2,y2),(x3,y3))，必须正交。"""
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if x1 != x2 and y1 != y2:
                raise ValueError("导线必须正交：%s -> %s" % ((x1, y1), (x2, y2)))
            self.wires.append((x1 + OX, y1 + OY, x2 + OX, y2 + OY))

    # ---------- 输出 ----------
    def xml(self):
        out = ['  <circuit name="%s">' % self.name,
               '    <a name="circuit" val="%s"/>' % self.name,
               '    <a name="clabel" val=""/>',
               '    <a name="clabelup" val="east"/>',
               '    <a name="clabelfont" val="%s"/>' % FONT,
               '    <a name="clabelcolor" val="#000000"/>']
        out += ['    <wire from="(%d,%d)" to="(%d,%d)"/>' % w for w in self.wires]
        out += self.parts
        out.append('  </circuit>')
        return "\n".join(out)


def project(*circuits, main=None):
    head = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
            '<project source="2.15.0.2.jar" version="1.0">\n'
            'This file is intended to be loaded by Logisim '
            'http://logisim.altervista.org\n')
    libs = [
        '  <lib desc="#Base" name="0">',
        '    <tool name="Text Tool">',
        _a("text", ""), _a("font", FONT), _a("color", "#000000"),
        _a("halign", "center"), _a("valign", "base"),
        '    </tool>',
        '  </lib>',
        '  <lib desc="#Gates" name="1"/>',
        '  <lib desc="#TTL" name="2"/>',
        '  <lib desc="#Wiring" name="3"/>',
        '  <lib desc="#Plexers" name="4"/>',
        '  <lib desc="#Arithmetic" name="5"/>',
        '  <lib desc="#Memory" name="6"/>',
        '  <lib desc="#I/O" name="7"/>',
        '  <main name="%s"/>' % (main or circuits[0].name),
        '  <options>',
        _a("gateUndefined", "ignore"), _a("simlimit", "1000"), _a("simrand", "0"),
        '  </options>',
        '  <mappings/>',
        toolbar(),
    ]
    return head + "\n".join(libs) + "\n" + \
        "\n".join(c.xml() for c in circuits) + "\n</project>\n"


# ---------------------------------------------------------------------------
# 样例：半加器 S=A⊕B、C=AB（5 个 NAND2）
# ---------------------------------------------------------------------------
def half_adder():
    """S = A⊕B，C = A·B，全用 NAND2：

        n1=(AB)′  n2=(A·n1)′  n3=(B·n1)′  S=(n2·n3)′  C=(n1·n1)′
    """
    c = Circuit("半加器")
    c.text(300, -150, "半加器   S = A⊕B   C = A·B", font=FONT)

    a = c.pin("A", 0, 0)
    b = c.pin("B", 0, 40)

    n1_in, n1 = c.gate("NAND Gate", 260, 20)     # (220,10) (220,30) -> (260,20)
    n2_in, n2 = c.gate("NAND Gate", 420, -60)    # (380,-70) (380,-50) -> (420,-60)
    n3_in, n3 = c.gate("NAND Gate", 420, 100)    # (380,90) (380,110) -> (420,100)
    s_in, s = c.gate("NAND Gate", 580, 20)       # (540,10) (540,30) -> (580,20)
    c_in, cy = c.gate("NAND Gate", 420, 240)     # (380,230) (380,250) -> (420,240)

    # A：竖干 x=140，一路到 n1.in1，一路绕到 n2.in1
    c.w(a, (140, 0), (140, 10), n1_in[0])
    c.w((140, 0), (140, -70), n2_in[0])

    # B：竖干 x=100 到 n1.in2；另一路走 y=300，从 x=330 通道进 n3.in2
    c.w(b, (100, 40), (100, 30), n1_in[1])
    c.w((100, 40), (100, 300), (330, 300), (330, 110), n3_in[1])

    # n1 输出：三条通道；到 C 门的那条走 x=270，避开 n3 的输入线
    c.w(n1, (290, 20), (290, -50), n2_in[1])
    c.w((290, 20), (320, 20), (320, 90), n3_in[0])
    c.w((290, 20), (270, 20), (270, 230), c_in[0])
    c.w((270, 230), (270, 250), c_in[1])

    # n2 / n3 -> S
    c.w(n2, (500, -60), (500, 10), s_in[0])
    c.w(n3, (500, 100), (500, 30), s_in[1])

    c.w(s, (720, 20), (820, 20))
    c.pin("S", 820, 20, output=True)
    c.w(cy, (720, 240), (820, 240))
    c.pin("C", 820, 240, output=True)

    return c


def main():
    circ = half_adder()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(project(circ))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
