# -*- coding: utf-8 -*-
"""Logisim .circ 工具链：环境解析 + 布局生成 + 几何审计 + 真值表。

单文件 CLI，供 agent 在无 GUI 环境下操作 Logisim：

    python logisim.py env                      # 打印解析到的 java / logisim 路径
    python logisim.py build-tools              # 编译 java/*.java -> java/classes
    python logisim.py pins a.circ              # 元件/引脚/导线几何（人读）
    python logisim.py audit a.circ             # 几何审计（悬空/未接/交叉/穿体/压字）
    python logisim.py render a.circ 电路名 out.png [scale]
    python logisim.py sim a.circ 电路名 [x,y ...]   # 用 Logisim 自己的仿真出真值表

设计原则：所有几何都问 Logisim 要（PinsDump），不手算、不猜；
真值表用 Logisim 的 Propagator（SimTable），不自己写求值器。
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
JAVA_SRC = SKILL / "java"
JAVA_CLS = JAVA_SRC / "classes"
TOOLS = ["PinsDump", "SimTable", "WireValues", "CircExport", "PinDump",
         "BoundsDump", "LibDump", "FactoryDump", "ToolbarDump"]

# selftest 用的最小时序电路：4 位 Counter + 手动 CLK（输入 Pin）
COUNTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
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
  <main name="ctr"/>
  <options>
    <a name="gateUndefined" val="ignore"/>
    <a name="simlimit" val="1000"/>
    <a name="simrand" val="0"/>
  </options>
  <mappings/>
  <toolbar/>
  <circuit name="ctr">
    <wire from="(400,320)" to="(480,320)"/>
    <comp lib="3" loc="(400,320)" name="Pin">
      <a name="facing" val="east"/>
      <a name="output" val="false"/>
      <a name="width" val="1"/>
      <a name="tristate" val="false"/>
      <a name="pull" val="none"/>
      <a name="label" val="CLK"/>
    </comp>
    <comp lib="6" loc="(500,300)" name="Counter">
      <a name="width" val="4"/>
      <a name="max" val="15"/>
    </comp>
  </circuit>
</project>
"""

# ---------------------------------------------------------------- 环境解析


def _java_version(java: str) -> str:
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True,
                           timeout=20)
        txt = (r.stderr or "") + (r.stdout or "")
        for line in txt.splitlines():
            if "version" in line:
                return line.strip().strip('"')
        return txt.strip().splitlines()[0] if txt.strip() else "?"
    except Exception as e:                                  # noqa: BLE001
        return "unusable: %s" % e


def _minor(java: str) -> int:
    """Java 主版本号，解析不出来返回 0。"""
    v = _java_version(java)
    for tok in v.replace('"', " ").replace(".", " ").split():
        if tok.isdigit():
            n = int(tok)
            return n - 1 if n == 1 else n                    # 1.8 -> 8
    return 0


JAVA_CANDIDATES = [
    os.environ.get("LOGISIM_JAVA"),
    os.environ.get("JAVA_HOME", "") and os.path.join(os.environ["JAVA_HOME"], "bin", "java.exe"),
    r"C:\Program Files\Zulu\zulu-17\bin\java.exe",
    r"C:\Program Files\Zulu\zulu-11\bin\java.exe",
    r"C:\Program Files\Java\jdk-17\bin\java.exe",
    r"C:\Program Files\Eclipse Adoptium\jdk-17\bin\java.exe",
    shutil.which("java"),
]


def find_java() -> str:
    """找一个能用的 java（>=8）。裸 java 常落到 1.7 JRE，会报“找不到主类”且无提示。"""
    tried = []
    for c in JAVA_CANDIDATES:
        if not c or not os.path.isfile(c):
            continue
        tried.append(c)
        if _minor(c) >= 8:
            return c
    raise SystemExit(
        "找不到可用的 java(>=8)。已试：\n  " + "\n  ".join(tried or ["(无)"]) +
        "\n设环境变量 LOGISIM_JAVA 指向 java.exe。")


def _walk_find(root, depth=4, maxdirs=4000):
    """深度受限地找 logisim（避免对着 C:\\ 全盘递归）。"""
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return None
    base = root.rstrip("\\/").count(os.sep)
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        seen += 1
        if seen > maxdirs:
            break
        if dirpath.count(os.sep) - base >= depth:
            dirnames[:] = []
        for fn in filenames:
            low = fn.lower()
            if low.startswith("logisim") and (low.endswith(".exe") or low.endswith(".jar")):
                return os.path.join(dirpath, fn)
    return None


def find_logisim(extra_roots=()) -> str:
    """.circ 的 classpath 可以直接写 logisim 的 exe（launch4j 把 jar 附在尾部），不用解包。"""
    env = os.environ.get("LOGISIM_EXE")
    if env and os.path.isfile(env):
        return env

    cur = Path(os.getcwd()).resolve()
    # 1) 当前目录及上级（浅层，先看平铺文件）
    for root in [cur] + list(cur.parents)[:3]:
        for fn in os.listdir(root):
            low = fn.lower()
            if low.startswith("logisim") and (low.endswith(".exe") or low.endswith(".jar")):
                return str(root / fn)
    # 2) 当前目录向下 4 层
    hit = _walk_find(cur)
    if hit:
        return hit
    # 3) 显式给的根 + 用户文档目录
    for root in list(extra_roots) + [os.path.expanduser("~/docs"),
                                     os.path.expanduser("~/Documents")]:
        hit = _walk_find(root, depth=5)
        if hit:
            return hit

    raise SystemExit(
        "找不到 logisim 可执行文件。设环境变量 LOGISIM_EXE=<path\\logisim-*.exe>，"
        "或把 logisim-hust-*.exe 放到工作目录下。")


class Env:
    def __init__(self):
        self.java = find_java()
        self.logisim = find_logisim()
        self.cp = self.logisim + os.pathsep + str(JAVA_CLS)

    def run(self, main: str, *args: str, timeout: int = 180,
            headless: bool = True) -> subprocess.CompletedProcess:
        ensure_tools(self)
        cmd = [self.java]
        if headless:
            cmd.append("-Djava.awt.headless=true")
        cmd += ["-cp", self.cp, main] + list(args)
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if "UnsupportedClassVersionError" in (r.stderr or ""):
            build_tools(self)            # 换了 java 版本：重编后重试一次
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        return r

    def __str__(self):
        return "java=%s (%s)\nlogisim=%s\ncp=%s\nclasses=%s" % (
            self.java, _java_version(self.java), self.logisim, self.cp,
            "ok" if (JAVA_CLS / "PinsDump.class").exists() else "缺失")


def ensure_tools(env: Env) -> None:
    if all((JAVA_CLS / (t + ".class")).exists() for t in ("PinsDump", "SimTable")):
        return
    build_tools(env)


def build_tools(env: Env | None = None) -> None:
    env = env or Env()
    javac = str(Path(env.java).with_name("javac.exe"))
    if not os.path.isfile(javac):
        raise SystemExit("找不到 javac（和 java 同目录）：" + javac)
    JAVA_CLS.mkdir(parents=True, exist_ok=True)
    srcs = sorted(str(p) for p in JAVA_SRC.glob("*.java"))
    base = [javac, "-encoding", "UTF-8", "-cp", env.logisim, "-d", str(JAVA_CLS)]
    # 固定 release 11：否则用 JDK 25 编出来的 class 在 java 11 上跑不了
    r = subprocess.run(base + ["--release", "11"] + srcs,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        r = subprocess.run(base + srcs, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("编译失败：\n" + (r.stdout or "") + (r.stderr or ""))
    print("compiled %d files -> %s" % (len(srcs), JAVA_CLS))


# ---------------------------------------------------------------- 读 TSV


def load_tsv(path) -> dict:
    circs = {}
    cur = None
    for line in open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if not f or not f[0]:
            continue
        if f[0] == "CIRC":
            cur = {"name": f[1], "comps": [], "ends": [], "wires": [], "attrs": {}}
            circs[cur["name"]] = cur
        elif f[0] == "COMP":
            cur["comps"].append({
                "factory": f[1], "idx": int(f[2]), "x": int(f[3]), "y": int(f[4]),
                "bounds": tuple(int(v) for v in f[5:9]), "label": f[9]})
        elif f[0] == "ATTR":
            cur["attrs"].setdefault(int(f[1]), {})[f[2]] = f[3]
        elif f[0] == "END":
            cur["ends"].append({"comp": int(f[1]), "pin": int(f[2]),
                                "x": int(f[3]), "y": int(f[4]), "dir": f[5]})
        elif f[0] == "WIRE":
            cur["wires"].append(tuple(int(v) for v in f[1:5]))
    return circs


def run_pinsdump(env: Env, circ: str) -> dict:
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".tsv")
    os.close(fd)
    try:
        r = env.run("PinsDump", circ, tmp)
        if r.returncode != 0 or not os.path.getsize(tmp):
            raise SystemExit("PinsDump 失败：\n" + (r.stderr or r.stdout))
        return load_tsv(tmp)
    finally:
        os.unlink(tmp)


# ---------------------------------------------------------------- 几何工具


def on_seg(p, w, strict=False):
    x, y = p
    x1, y1, x2, y2 = w
    if x1 == x2 == x:
        return (min(y1, y2) < y < max(y1, y2)) if strict else (min(y1, y2) <= y <= max(y1, y2))
    if y1 == y2 == y:
        return (min(x1, x2) < x < max(x1, x2)) if strict else (min(x1, x2) <= x <= max(x1, x2))
    return False


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def build_nets(c):
    """连通性：导线端点 + T 接 + 引脚落在线身上（Logisim 三样都算连上）。"""
    d = DSU()
    for w in c["wires"]:
        d.union((w[0], w[1]), (w[2], w[3]))
    pts = set()
    for w in c["wires"]:
        pts.add((w[0], w[1]))
        pts.add((w[2], w[3]))
    for p in list(pts):
        for w in c["wires"]:
            if p in ((w[0], w[1]), (w[2], w[3])):
                continue
            if on_seg(p, w, strict=True):
                d.union(p, (w[0], w[1]))
    for e in c["ends"]:
        p = (e["x"], e["y"])
        for w in c["wires"]:
            if on_seg(p, w):
                d.union(p, (w[0], w[1]))
    return d


def junctions(c):
    """真正的结点（Logisim 会画实心圆点）：端点/引脚/线段内部三者度数 >= 3。"""
    ends = collections.Counter()
    for w in c["wires"]:
        ends[(w[0], w[1])] += 1
        ends[(w[2], w[3])] += 1
    pins = collections.Counter((e["x"], e["y"]) for e in c["ends"])
    out = []
    for p in set(ends) | set(pins):
        deg = ends.get(p, 0) + pins.get(p, 0)
        for w in c["wires"]:
            if p in ((w[0], w[1]), (w[2], w[3])):
                continue
            if on_seg(p, w, strict=True):
                deg += 1
        if deg >= 3:
            out.append((p, deg))
    return ends, pins, out


def crossings(c):
    out = []
    ws = c["wires"]
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            if (a[1] == a[3]) == (b[1] == b[3]):
                continue
            h, v = (a, b) if a[1] == a[3] else (b, a)
            hy, vx = h[1], v[0]
            hx1, hx2 = sorted((h[0], h[2]))
            vy1, vy2 = sorted((v[1], v[3]))
            if hx1 < vx < hx2 and vy1 < hy < vy2:
                out.append((vx, hy))
    return out


def overlaps(c):
    """同向共线且有交叠的导线：Logisim 不会合并，看起来像一根线，实际是两根。"""
    out = []
    ws = c["wires"]
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            if a[1] == a[3] == b[1] == b[3] and a[1] == b[1]:
                lo1, hi1 = sorted((a[0], a[2]))
                lo2, hi2 = sorted((b[0], b[2]))
                if max(lo1, lo2) < min(hi1, hi2):
                    out.append((a, b))
            elif a[0] == a[2] == b[0] == b[2] and a[0] == b[0]:
                lo1, hi1 = sorted((a[1], a[3]))
                lo2, hi2 = sorted((b[1], b[3]))
                if max(lo1, lo2) < min(hi1, hi2):
                    out.append((a, b))
    return out


def through_body(c, margin=2):
    """导线穿过元件外接矩形内部。端点正好落在引脚上不算。"""
    out = []
    pinpts = {(e["x"], e["y"]) for e in c["ends"]}
    for comp in c["comps"]:
        if comp["factory"] in ("Text", "Tunnel", "Probe"):
            continue
        bx, by, bw, bh = comp["bounds"]
        if bw <= 0 or bh <= 0:
            continue
        for w in c["wires"]:
            x1, y1, x2, y2 = w
            # 这根线是否以该元件引脚为端点（是就不算穿体）
            if any(p in ((x1, y1), (x2, y2)) and on_seg(p, w) and
                   bx - 1 <= p[0] <= bx + bw + 1 and by - 1 <= p[1] <= by + bh + 1
                   for p in pinpts):
                continue
            if y1 == y2:
                if by + margin < y1 < by + bh - margin:
                    lo, hi = sorted((x1, x2))
                    if max(lo, bx + margin) < min(hi, bx + bw - margin):
                        out.append((comp, w))
            elif x1 == x2:
                if bx + margin < x1 < bx + bw - margin:
                    lo, hi = sorted((y1, y2))
                    if max(lo, by + margin) < min(hi, by + bh - margin):
                        out.append((comp, w))
    return out


def text_over_wire(c, margin=3):
    """文字被导线穿过。用 margin 避开"文字底边正好压在线顶"这种贴边情况。

    Logisim 的 Text 外接矩形按 valign=base 算，底边常在基线附近；
    真正的压字是导线从字身中间穿过，不是贴着下边缘走。
    """
    out = []
    for comp in c["comps"]:
        if comp["factory"] != "Text":
            continue
        bx, by, bw, bh = comp["bounds"]
        if bw <= 0 or bh <= 0:
            continue
        for w in c["wires"]:
            x1, y1, x2, y2 = w
            if y1 == y2 and by + margin < y1 < by + bh - margin:
                lo, hi = sorted((x1, x2))
                if max(lo, bx + margin) < min(hi, bx + bw - margin):
                    out.append((comp, w))
            elif x1 == x2 and bx + margin < x1 < bx + bw - margin:
                lo, hi = sorted((y1, y2))
                if max(lo, by + margin) < min(hi, by + bh - margin):
                    out.append((comp, w))
    return out


def drivers(c):
    """按网络统计驱动器，预测 Logisim 的红线（E）。

    - `Power` 恒 1、`Ground` 恒 0 → 两者同网是**确定**的 E（电源短路）。
    - 其余输出脚（输入 Pin、门输出、DipSwitch、Constant、Clock…）的值要跑起来才知道，
      多个同网是**可能**的 E。两个同值驱动 Logisim 会合并成该值，不一定报红。
    """
    d = build_nets(c)
    out = collections.defaultdict(list)
    for e in c["ends"]:
        if e["dir"] not in ("OUT", "INOUT"):
            continue
        cf = c["comps"][e["comp"]]["factory"]
        if cf == "Text":
            continue
        attrs = c["attrs"].get(e["comp"], {})
        root = d.find((e["x"], e["y"]))
        out[root].append({"factory": cf, "label": c["comps"][e["comp"]]["label"],
                          "point": (e["x"], e["y"]), "attrs": attrs})
    return out


def driver_problems(c):
    """返回 (确定短路, 可能多驱动)。"""
    hard, soft = [], []
    for root, ds in drivers(c).items():
        if len(ds) < 2:
            continue
        kinds = {z["factory"] for z in ds}
        pts = [z["point"] for z in ds]
        desc = " + ".join("%s%s%s" % (z["factory"],
                                      "/" + z["label"] if z["label"] else "",
                                      str(z["point"])) for z in ds)
        if "Power" in kinds and "Ground" in kinds:
            hard.append((pts[0], desc))
            continue
        signal = [z for z in ds if z["factory"] not in ("Power", "Ground")]
        if len(signal) >= 2:
            soft.append((pts[0], desc))
    return hard, soft


def texts_overlap(c, margin=2):
    """两个 Text 的外接矩形重叠：打印出来是糊在一起的字。"""
    ts = [z for z in c["comps"] if z["factory"] == "Text"
          and z["bounds"][2] > 0 and z["bounds"][3] > 0]
    out = []
    for i, a in enumerate(ts):
        ax, ay, aw, ah = a["bounds"]
        for b in ts[i + 1:]:
            bx, by, bw, bh = b["bounds"]
            if (ax + margin < bx + bw and bx + margin < ax + aw and
                    ay + margin < by + bh and by + margin < ay + ah):
                out.append((a, b))
    return out


def duplicate_locs(c):
    """同一坐标上压了多个元件。DipSwitch 压在 SPDT_SEL 的 S 脚上是合法用法。"""
    by = collections.defaultdict(list)
    for z in c["comps"]:
        by[(z["x"], z["y"])].append(z)
    out = []
    for p, zs in by.items():
        if len(zs) < 2:
            continue
        names = {z["factory"] for z in zs}
        if "DipSwitch" in names and (names - {"DipSwitch"}) & {"SPDT_SEL", "SPDT_SW"}:
            continue
        out.append((p, [z["factory"] for z in zs]))
    return out


# ---------------------------------------------------------------- 子命令


def cmd_env(args):
    env = Env()
    print(env)


def cmd_build(args):
    build_tools(Env())


def cmd_selftest(args):
    """一条命令验证整条链路：编译 → 生成模板 → 审计 → 真值表 → 出图。"""
    import tempfile
    ok = True

    def step(name, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        print("  [%s] %-8s %s" % ("PASS" if passed else "FAIL", name, detail))

    env = Env()
    print("java     = %s" % env.java)
    print("logisim  = %s" % env.logisim)
    build_tools(env)

    tmp = tempfile.mkdtemp(prefix="logisim-selftest-")
    try:
        shutil.copy(str(SKILL / "templates" / "make_circ.py"), tmp)
        r = subprocess.run([sys.executable, "make_circ.py"], cwd=tmp,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        circ = os.path.join(tmp, "新建电路.circ")
        step("生成", r.returncode == 0 and os.path.exists(circ),
             circ if r.returncode == 0 else (r.stderr or r.stdout)[-200:])

        def cli(*a):
            return subprocess.run([sys.executable, str(HERE / "logisim.py"), *a],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")

        r = cli("audit", circ)
        step("审计", "错误项合计：0" in r.stdout,
             [ln for ln in r.stdout.splitlines() if "错误项合计" in ln][:1])

        r = cli("sim", circ, "半加器")
        want = ["00 -> 0 0", "10 -> 1 0", "01 -> 1 0", "11 -> 0 1"]
        got = [ln.strip() for ln in r.stdout.splitlines()]
        step("真值表", all(w in got for w in want), " / ".join(want))

        png = os.path.join(tmp, "half.png")
        r = cli("render", circ, "半加器", png, "2")
        step("出图", os.path.exists(png) and os.path.getsize(png) > 1000,
             png)

        r = cli("values", circ, "半加器", "01")
        step("电平", "红(E)=0" in r.stdout, "红(E)=0")

        # 时序模式：临时造一个 4 位计数器（Counter + 手动 CLK）
        seq = os.path.join(tmp, "counter.circ")
        with open(seq, "w", encoding="utf-8") as f:
            f.write(COUNTER_XML)
        r = cli("sim", seq, "ctr", "500,300", "--clock", "CLK", "--ticks", "3")
        rows = [ln.strip() for ln in r.stdout.splitlines()]
        step("时序", all(w in rows for w in
                        ["t1 -> 0001", "t2 -> 0010", "t3 -> 0011"]),
             "t1..t3 = 0001/0010/0011")

        print("\n结果：%s" % ("全部通过" if ok else "有失败项，见上"))
        sys.exit(0 if ok else 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_check(args):
    """结构检查：要求哪些引脚在、禁止哪些元件/库、main 电路别太大。

    与 audit 的分工：audit 看“画对没有”（几何/连接），check 看“做对没有”（题面约束）。
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(args.circ).getroot()
    libs = {el.get("name"): el.get("desc") for el in root.findall("lib")}
    circuits = {}
    for el in root.findall("circuit"):
        comps = []
        for comp in el.findall("comp"):
            attrs = {x.get("name"): x.get("val") for x in comp.findall("a")}
            comps.append({"name": comp.get("name"), "lib": comp.get("lib"),
                          "loc": comp.get("loc"), "attrs": attrs})
        circuits[el.get("name")] = comps
    main_el = root.find("main")
    which = args.circuit or (main_el.get("name") if main_el is not None else None)
    if which not in circuits:
        sys.exit("check: 找不到电路 %r（有：%s）" % (which, ", ".join(circuits)))
    comps = circuits[which]

    bad = 0

    def verdict(ok, tag, detail=""):
        nonlocal bad
        if not ok:
            bad += 1
        print("  [%s] %-10s %s" % ("PASS" if ok else "FAIL", tag, detail))

    print("### %s   元件 %d（不含 Text）" %
          (which, len([c for c in comps if c["name"] != "Text"])))

    for spec in args.require or []:
        parts = spec.split(":")
        label, width = parts[0], parts[1] if len(parts) > 1 else "1"
        want_out = len(parts) > 2 and parts[2].lower() in ("out", "output", "o")
        hit = [c for c in comps if c["name"] == "Pin"
               and c["attrs"].get("label") == label]
        got = [(c["attrs"].get("width", "1"),
                c["attrs"].get("output", "false").lower() == "true") for c in hit]
        ok = any(w == width and o == want_out for w, o in got)
        verdict(ok, "引脚 " + spec,
                "" if ok else "实际：%s" % (got or "没有这个 Pin"))

    if args.max_comps:
        n = len([c for c in comps if c["name"] != "Text"])
        verdict(n <= args.max_comps, "元件数",
                "%d ≤ %d" % (n, args.max_comps) if n <= args.max_comps
                else "%d > %d" % (n, args.max_comps))

    names = set()
    for spec in args.forbid or []:
        names |= {s.strip() for s in spec.split(",") if s.strip()}
    hit = [c for c in comps if c["name"] in names]
    verdict(not hit, "禁用元件",
            "无" if not hit else "出现 %s" % sorted({c["name"] for c in hit}))

    for spec in args.forbid_lib or []:
        want = spec if spec.startswith("#") else "#" + spec
        hit = [c for c in comps if libs.get(c["lib"]) == want]
        verdict(not hit, "禁用库 " + want,
                "无" if not hit else "出现 %d 个：%s" % (
                    len(hit), sorted({c["name"] for c in hit})))

    if args.no_halt:
        hit = [c for c in comps if c["name"] == "Halt"]
        verdict(not hit, "无 halt", "无" if not hit else "交付件里不该留 halt")

    print("检查项失败：%d" % bad)
    sys.exit(1 if bad else 0)


def cmd_pins(args):
    env = Env()
    for name, c in run_pinsdump(env, args.circ).items():
        print("=== %s   元件 %d  导线 %d  引脚 %d" %
              (name, len(c["comps"]), len(c["wires"]), len(c["ends"])))
        by = collections.defaultdict(list)
        for e in c["ends"]:
            by[e["comp"]].append(e)
        for comp in sorted(c["comps"], key=lambda z: (z["y"], z["x"])):
            pins = sorted(by.get(comp["idx"], []), key=lambda e: e["pin"])
            lab = (" label=" + comp["label"]) if comp["label"] else ""
            print("  %-18s loc=(%d,%d) bounds=%s%s" %
                  (comp["factory"], comp["x"], comp["y"], comp["bounds"], lab))
            if pins:
                print("       " + "  ".join(
                    "p%d(%+d,%+d)%s" % (e["pin"], e["x"] - comp["x"],
                                        e["y"] - comp["y"], e["dir"][0])
                    for e in pins))


def cmd_audit(args):
    env = Env()
    circs = run_pinsdump(env, args.circ)
    bad = 0
    for name, c in circs.items():
        if args.circuit and name != args.circuit:
            continue
        print("=" * 72)
        print("### %s   元件 %d  导线 %d  引脚 %d" %
              (name, len(c["comps"]), len(c["wires"]), len(c["ends"])))
        ends, pins, dots = junctions(c)
        pinpts = set(pins)

        dangle = []
        for p, n in ends.items():
            if p in pinpts or n >= 2:
                continue
            if any(on_seg(p, w, strict=True) for w in c["wires"]):
                continue
            dangle.append(p)

        unconnected = []
        for e in c["ends"]:
            p = (e["x"], e["y"])
            if any(on_seg(p, w) for w in c["wires"]):
                continue
            if pins.get(p, 0) >= 2:          # 引脚对引脚直接压在一起（DipSwitch 压在 S 上）
                continue
            cf = c["comps"][e["comp"]]["factory"]
            if cf == "Text":
                continue
            unconnected.append((cf, c["comps"][e["comp"]]["label"], p, e["dir"]))

        cross = crossings(c)
        over = overlaps(c)
        thru = through_body(c)
        textw = text_over_wire(c)
        hard, soft = driver_problems(c)
        tdup = texts_overlap(c)
        dupl = duplicate_locs(c)

        def line(tag, n, head="", level="ERROR"):
            nonlocal bad
            flag = "OK  " if n == 0 else level
            print("  [%s] %-10s %d%s" % (flag, tag, n, head))
            if n and level == "ERROR":
                bad += 1

        line("悬空端点", len(dangle), "  " + str(dangle[:12]))
        line("未接引脚", len(unconnected), "  " + str(unconnected[:12]))
        line("同向重叠", len(over), "  %d 组" % len(over) if over else "")
        line("穿元件体", len(thru),
             "  " + str([(x[0]["factory"], x[0]["label"], x[1]) for x in thru[:6]]))
        line("文字压线", len(textw),
             "  " + str([(x[0]["x"], x[0]["y"], x[1]) for x in textw[:6]]))
        line("电源短路", len(hard), "  " + str([z[0] for z in hard[:6]]))
        for _, desc in hard[:6]:
            print("        ! 同一网络接了 " + desc + "（Logisim 里必是红色 E）")
        for tag, items, note in (
                ("多驱动", soft, "两个以上输出脚同网，值不同就会变红（E）"),
                ("文字重叠", tdup, "两段文字外接矩形重叠，打印后糊在一起"),
                ("元件同坐标", dupl, "同一坐标压了多个元件，GUI 里点选会互相遮挡")):
            if tag == "文字重叠":
                head = "  " + str([(it[0]["x"], it[0]["y"]) for it in items[:8]]) if items else ""
            else:
                head = "  " + str([it[0] for it in items[:8]]) if items else ""
            print("  [%s] %-10s %d%s" % ("WARN" if items else "OK  ", tag, len(items), head))
            for it in items[:4]:
                if tag == "多驱动":
                    print("        ! " + it[1] + " —— " + note)
                elif tag == "文字重叠":
                    print("        ! Text(%d,%d) 与 Text(%d,%d) 重叠"
                          % (it[0]["x"], it[0]["y"], it[1]["x"], it[1]["y"]))
                else:
                    print("        ! (%d,%d) 上是 %s" % (it[0][0], it[0][1], it[1]))

        # 交叉点：只统计数量。Logisim 约定“有圆点=连、无圆点=交叉”，
        # 距离远近不影响判读，所以默认只报 INFO；想要更疏的版式再加 --cross-gap N。
        near = []
        if args.cross_gap > 0:
            for (x, y) in cross:
                if not dots:
                    break
                dd, dp = min((abs(dx - x) + abs(dy - y), (dx, dy)) for (dx, dy), _ in dots)
                if dd <= args.cross_gap:
                    near.append(((x, y), dp, dd))
        flag = "WARN" if near else ("INFO" if cross else "OK  ")
        print("  [%s] %-10s %d%s" % (flag, "交叉点", len(cross),
                                     "" if not cross else "  " + str(cross)))
        for it in near:
            print("        ! 交叉 %s 离结点 %s 仅 %d 格（风格提示，不影响判读）"
                  % (it[0], it[1], it[2]))

        pw = [z for z in c["comps"] if z["factory"] == "Power"]
        gd = [z for z in c["comps"] if z["factory"] == "Ground"]
        print("  [INFO] 电源符号 Power x%d %s  Ground x%d %s" %
              (len(pw), [(z["x"], z["y"]) for z in pw],
               len(gd), [(z["x"], z["y"]) for z in gd]))
    print("=" * 72)
    print("错误项合计：%d   （WARN 不影响仿真，只影响可读性）" % bad)
    sys.exit(1 if bad else 0)


def cmd_render(args):
    env = Env()
    out = args.out
    scale = str(args.scale)
    if args.circuit.upper() == "ALL":
        os.makedirs(out, exist_ok=True)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    r = env.run("CircExport", args.circ, args.circuit, out, scale)
    msg = ((r.stdout or "") + (r.stderr or "")).strip()
    print(msg or ("（无输出，返回码 %d）" % r.returncode))
    sys.exit(r.returncode)


def cmd_values(args):
    env = Env()
    r = env.run("WireValues", args.circ, args.circuit, args.combo or "")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if args.only_red:
        lines = [ln for ln in out.splitlines() if "<<< E" in ln or "合计" in ln]
        print("\n".join(lines) or "（没有红线）")
    else:
        print(out)
    sys.exit(0 if "红(E)=0" in out else 1)


def cmd_sim(args):
    env = Env()
    extra = []
    if args.clock:
        extra += ["--clock", args.clock]
    if args.ticks:
        extra += ["--ticks", str(args.ticks)]
    if args.combo:
        extra += ["--combo", args.combo]
    r = env.run("SimTable", args.circ, args.circuit, *(list(args.probes) + extra))
    print(((r.stdout or "") + (r.stderr or "")).strip())
    sys.exit(r.returncode)


def main(argv=None):
    p = argparse.ArgumentParser(description="Logisim .circ 无 GUI 工具链")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("env", help="打印解析到的 java / logisim").set_defaults(fn=cmd_env)
    sub.add_parser("build-tools", help="编译 java/*.java").set_defaults(fn=cmd_build)
    sub.add_parser("selftest", help="端到端自检（编译→生成→审计→仿真→出图）") \
        .set_defaults(fn=cmd_selftest)

    q = sub.add_parser("pins", help="打印元件/引脚几何")
    q.add_argument("circ")
    q.set_defaults(fn=cmd_pins)

    q = sub.add_parser("audit", help="几何审计（有问题返回码 1）")
    q.add_argument("circ")
    q.add_argument("circuit", nargs="?")
    q.add_argument("--cross-gap", type=int, default=0, metavar="N",
                   help="可选：交叉点离结点 <N 格时提示（默认 0=不提示；纯风格，不影响判读）")
    q.set_defaults(fn=cmd_audit)

    q = sub.add_parser("check", help="结构检查：引脚在不在、有没有用禁用的元件/库")
    q.add_argument("circ")
    q.add_argument("circuit", nargs="?", help="电路名；默认取 <main>")
    q.add_argument("--require", action="append", metavar="LABEL:WIDTH:in|out",
                   help="要求存在某个 Pin（可重复），如 A:1:in、RESULT:8:out")
    q.add_argument("--forbid", action="append", metavar="NAME[,NAME]",
                   help="禁止出现的工厂名（可重复），如 Adder,Subtractor")
    q.add_argument("--forbid-lib", action="append", metavar="N",
                   help="禁止出现的库，写 desc 号或 #Arithmetic（可重复）")
    q.add_argument("--max-comps", type=int, help="非 Text 元件数上限")
    q.add_argument("--no-halt", action="store_true", help="交付件不允许有 Halt")
    q.set_defaults(fn=cmd_check)

    q = sub.add_parser("render", help="导出 PNG（打印视图）")
    q.add_argument("circ")
    q.add_argument("circuit", help="电路名，或 ALL")
    q.add_argument("out")
    q.add_argument("scale", nargs="?", type=float, default=4.0)
    q.set_defaults(fn=cmd_render)

    q = sub.add_parser("values", help="导线电平/找红线（E=冲突）")
    q.add_argument("circ")
    q.add_argument("circuit")
    q.add_argument("combo", nargs="?", default="",
                   help="DipSwitch 原始值位串，从左到右=开关从上到下，如 010")
    q.add_argument("--red", dest="only_red", action="store_true", help="只列红线")
    q.set_defaults(fn=cmd_values)

    q = sub.add_parser("sim", help="真值表 / 逐拍波形（用 Logisim 仿真）")
    q.add_argument("circ")
    q.add_argument("circuit")
    q.add_argument("probes", nargs="*", help="探测点 x,y；省略则取所有 LED/输出 Pin")
    q.add_argument("--clock", metavar="LABEL", help="时序模式：用这个 1 位输入当时钟")
    q.add_argument("--ticks", type=int, metavar="N", help="时序模式：跑 N 个上升沿")
    q.add_argument("--combo", metavar="010", help="时序模式：其余输入固定的位串")
    q.set_defaults(fn=cmd_sim)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
