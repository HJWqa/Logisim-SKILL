import java.io.File;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.Project;

/**
 * 扫一个电路里所有"可点的输入"，打印任意探测点的真值表 / 逐拍波形。
 *
 * 组合模式（默认）：枚举所有 1 位 DipSwitch（或输入 Pin）的组合，每个组合一行。
 * 时序模式（--clock LABEL --ticks N）：把 LABEL 那个输入当手动时钟，每个上升沿一行。
 *
 * 驱动源按优先级自动选择：
 *   1. 1 位 DipSwitch（接线图里当扳手用）；
 *   2. 没有 DipSwitch 时，退化为输入 Pin（output=false，且 label 不像电源脚）。
 * --clock 指定时序模式时，两类都算数据输入，被指定的那个单独当时钟。
 *
 * 探测点可以写在参数里（x,y），不写就自动取所有 LED + 输出 Pin。
 *
 * 只调用同步的 CircuitState.getPropagator().propagate()，不启动 Simulator 线程，
 * 避免"设值 + 异步传播"互相踩（会偶发 Propagator NPE）。
 *
 * 用法：
 *   java -cp logisim.exe;classes SimTable in.circ 电路名 [x,y ...]
 *   java -cp logisim.exe;classes SimTable in.circ 电路名 [x,y ...] --clock CLK --ticks 8 [--combo 010]
 *
 * 位串顺序 = 驱动从上到下（y 小在前）；0 = 扳手朝上 = 逻辑 1（只对 SPDT_SEL 成立）。
 */
public class SimTable {
    public static void main(String[] args) {
        try {
            run(args);
        } catch (Throwable t) {
            t.printStackTrace();
            System.exit(1);
        }
        System.exit(0);
    }

    static void run(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: SimTable <circ> <circuit> [x,y ...] "
                    + "[--clock LABEL --ticks N] [--combo 010]");
            System.exit(2);
        }
        String file = args[0];
        String circuit = args[1];

        String clockLabel = null;
        int ticks = 0;
        String combo = "";
        List<String> probeArgs = new ArrayList<>();
        for (int i = 2; i < args.length; i++) {
            String a = args[i];
            if (a.equals("--clock") && i + 1 < args.length) {
                clockLabel = args[++i];
            } else if (a.startsWith("--clock=")) {
                clockLabel = a.substring(8);
            } else if (a.equals("--ticks") && i + 1 < args.length) {
                ticks = Integer.parseInt(args[++i]);
            } else if (a.startsWith("--ticks=")) {
                ticks = Integer.parseInt(a.substring(8));
            } else if (a.equals("--combo") && i + 1 < args.length) {
                combo = args[++i];
            } else if (a.startsWith("--combo=")) {
                combo = a.substring(8);
            } else {
                probeArgs.add(a);
            }
        }
        if (clockLabel != null && ticks <= 0) {
            System.err.println("--clock 需要配合 --ticks N（N>0）");
            System.exit(2);
        }

        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile f = loader.openLogisimFile(new File(file));
        Project proj = new Project(f);
        Circuit circ = f.getCircuit(circuit);
        if (circ == null) {
            System.err.println("no circuit " + circuit);
            for (Circuit c : f.getCircuits()) System.err.println("  have: " + c.getName());
            System.exit(3);
        }

        Component clock = clockLabel == null ? null : findByLabel(circ, clockLabel);
        if (clockLabel != null && clock == null) {
            System.err.println("找不到标签为 " + clockLabel + " 的 Pin/DipSwitch；"
                    + "时序模式要一个手动的 1 位输入当时钟（不要用 Clock 元件）");
            System.exit(4);
        }

        List<Component> drivers = new ArrayList<>();
        if (clock != null) {
            // 时序模式：DipSwitch 和输入 Pin 都算数据输入，时钟单独拿出来
            for (Component c : circ.getNonWires()) {
                if (c == clock) continue;
                if (isDataInput(c)) drivers.add(c);
            }
        } else {
            for (Component c : circ.getNonWires()) {
                if ("DipSwitch".equals(c.getFactory().getName()) && isOneBit(c)) drivers.add(c);
            }
            if (drivers.isEmpty()) {
                for (Component c : circ.getNonWires()) {
                    if (isInputPin(c)) drivers.add(c);
                }
            }
        }
        boolean viaPins = drivers.isEmpty() || !"DipSwitch".equals(drivers.get(0).getFactory().getName());
        drivers.sort(Comparator
                .comparingInt((Component c) -> c.getLocation().getY())
                .thenComparingInt(c -> c.getLocation().getX()));

        List<Location> probes = new ArrayList<>();
        List<String> probeNames = new ArrayList<>();
        if (!probeArgs.isEmpty()) {
            for (String s : probeArgs) {
                String[] xy = s.split(",");
                probes.add(Location.create(Integer.parseInt(xy[0].trim()),
                        Integer.parseInt(xy[1].trim())));
                probeNames.add(s);
            }
        } else {
            for (Component c : circ.getNonWires()) {
                String n = c.getFactory().getName();
                Object lab = c.getAttributeSet().getValue(StdAttr.LABEL);
                String s = lab == null ? "" : lab.toString();
                boolean isLed = "LED".equals(n);
                boolean isOutPin = "Pin".equals(n) && isOutput(c);
                if (!isLed && !isOutPin) continue;
                if (s.matches("^U\\d+-(?:7|14)$")) continue;
                probes.add(c.getLocation());
                probeNames.add((s.isEmpty() ? n : s) + c.getLocation());
            }
        }

        CircuitState state = new CircuitState(proj, circ);
        state.getPropagator().propagate();

        if (clock != null) {
            System.out.print("clock(" + clockLabel + ")" + clock.getLocation()
                    + "  ticks=" + ticks + "  combo=" + (combo.isEmpty() ? "0…" : combo));
            System.out.print("  data:");
            for (Component c : drivers) System.out.print(" " + c.getLocation());
            System.out.print("  probes:");
            for (String s : probeNames) System.out.print(" " + s);
            System.out.println();

            for (int i = 0; i < drivers.size(); i++) {
                int bit = i < combo.length() ? combo.charAt(i) - '0' : 0;
                apply(state, drivers.get(i), bit);
            }
            apply(state, clock, 0);
            state.getPropagator().propagate();
            System.out.println("t0 ->" + read(state, probes));

            for (int t = 1; t <= ticks; t++) {
                apply(state, clock, 1);
                state.getPropagator().propagate();
                apply(state, clock, 0);
                state.getPropagator().propagate();
                System.out.println("t" + t + " ->" + read(state, probes));
            }
            System.out.flush();
            return;
        }

        System.out.print("drivers(" + (viaPins ? "Pin" : "DipSwitch") + "):");
        for (Component c : drivers) System.out.print(" " + c.getLocation());
        System.out.print("  probes:");
        for (String s : probeNames) System.out.print(" " + s);
        System.out.println();

        for (int c0 = 0; c0 < (1 << drivers.size()); c0++) {
            for (int i = 0; i < drivers.size(); i++) {
                apply(state, drivers.get(i), (c0 >> i) & 1);
            }
            state.getPropagator().propagate();

            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < drivers.size(); i++) sb.append((c0 >> i) & 1);
            sb.append(" ->").append(read(state, probes));
            System.out.println(sb);
        }
        System.out.flush();
    }

    static String read(CircuitState state, List<Location> probes) {
        StringBuilder sb = new StringBuilder();
        for (Location l : probes) {
            Value v = state.getValue(l);
            sb.append(' ').append(v == null ? "null" : v.toDisplayString());
        }
        return sb.toString();
    }

    static void apply(CircuitState state, Component c, int bit) throws Exception {
        if ("Pin".equals(c.getFactory().getName())) {
            setPin(state, c, bit);
        } else {
            setSwitch(state, c, bit);
        }
        state.markComponentAsDirty(c);
    }

    static Component findByLabel(Circuit circ, String label) {
        for (Component c : circ.getNonWires()) {
            String n = c.getFactory().getName();
            if (!"Pin".equals(n) && !"DipSwitch".equals(n)) continue;
            Object lab = c.getAttributeSet().getValue(StdAttr.LABEL);
            if (lab != null && label.equals(lab.toString())) return c;
        }
        return null;
    }

    static boolean isOneBit(Component c) {
        Object ns = c.getAttributeSet().getValue(
                c.getAttributeSet().getAttribute("NSwitches"));
        return ns == null || Integer.parseInt(ns.toString()) == 1;
    }

    static boolean isInputPin(Component c) {
        if (!"Pin".equals(c.getFactory().getName())) return false;
        if (isOutput(c)) return false;
        Object lab = c.getAttributeSet().getValue(StdAttr.LABEL);
        String s = lab == null ? "" : lab.toString();
        return !s.matches("^U\\d+-(?:7|14)$");
    }

    static boolean isDataInput(Component c) {
        String n = c.getFactory().getName();
        if ("DipSwitch".equals(n)) return isOneBit(c);
        return isInputPin(c);
    }

    static boolean isOutput(Component c) {
        Object out = c.getAttributeSet().getValue(
                c.getAttributeSet().getAttribute("output"));
        return out != null && Boolean.parseBoolean(out.toString());
    }

    /** DipSwitch 的运行时状态藏在私有字段 vals[] 里。 */
    static void setSwitch(CircuitState state, Component c, int bit) throws Exception {
        Object data = state.getInstanceState(c).getData();
        java.lang.reflect.Field f = data.getClass().getDeclaredField("vals");
        f.setAccessible(true);
        Value[] vals = (Value[]) f.get(data);
        vals[0] = Value.createKnown(BitWidth.create(1), bit);
    }

    /** Pin 有公开的 setValue(InstanceState, Value)，不用反射。 */
    static void setPin(CircuitState state, Component c, int bit) {
        com.cburch.logisim.instance.InstanceState is = state.getInstanceState(c);
        ((com.cburch.logisim.std.wiring.Pin) c.getFactory())
                .setValue(is, Value.createKnown(BitWidth.create(1), bit));
        is.fireInvalidated();
    }
}
