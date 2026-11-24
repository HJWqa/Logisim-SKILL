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
 * 扫所有 1 位 DipSwitch（按 y 从上到下 = A、B、C…），打印探测点的值。
 *
 * 只调用同步的 CircuitState.getPropagator().propagate()，不启动 Simulator 线程，
 * 避免“设值 + 异步传播”互相踩（会偶发 Propagator NPE）。
 *
 * 用法：java -cp logisim.exe;classes CheckDips in.circ 电路名 x1,y1 x2,y2 ...
 */
public class CheckDips {
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
        String file = args[0];
        String circuit = args[1];

        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile f = loader.openLogisimFile(new File(file));
        Project proj = new Project(f);
        Circuit circ = f.getCircuit(circuit);
        if (circ == null) {
            throw new RuntimeException("no circuit " + circuit);
        }

        List<Component> dips = new ArrayList<>();
        for (Component c : circ.getNonWires()) {
            if ("DipSwitch".equals(c.getFactory().getName())) {
                dips.add(c);
            }
        }
        dips.sort(Comparator.comparingInt(c -> c.getLocation().getY()));

        List<Location> probes = new ArrayList<>();
        for (int i = 2; i < args.length; i++) {
            String[] xy = args[i].split(",");
            probes.add(Location.create(Integer.parseInt(xy[0]), Integer.parseInt(xy[1])));
        }

        CircuitState state = new CircuitState(proj, circ);
        state.getPropagator().propagate();

        System.out.print("switches:");
        for (Component c : dips) {
            System.out.print(" " + c.getAttributeSet().getValue(StdAttr.LABEL)
                    + "@" + c.getLocation());
        }
        System.out.print("  probes:");
        for (Location l : probes) {
            System.out.print(" " + l);
        }
        System.out.println();

        for (int combo = 0; combo < (1 << dips.size()); combo++) {
            for (int i = 0; i < dips.size(); i++) {
                Component c = dips.get(i);
                Object data = state.getInstanceState(c).getData();
                java.lang.reflect.Field valsField =
                        data.getClass().getDeclaredField("vals");
                valsField.setAccessible(true);
                Value[] vals = (Value[]) valsField.get(data);
                vals[0] = Value.createKnown(BitWidth.create(1), (combo >> i) & 1);
                state.markComponentAsDirty(c);
            }
            state.getPropagator().propagate();

            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < dips.size(); i++) {
                sb.append((combo >> i) & 1);
            }
            sb.append(" ->");
            for (Location l : probes) {
                Value v = state.getValue(l);
                sb.append(' ').append(v == null ? "null" : v.toDisplayString());
            }
            System.out.println(sb);
        }
        System.out.flush();
    }
}
