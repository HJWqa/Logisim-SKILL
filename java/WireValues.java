import java.io.File;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;

/**
 * 打印一个电路里每根导线的当前值，专门用来看 Logisim 里"红线"是哪几根。
 *
 * Logisim 的电平配色：绿=1、深绿=0、蓝=x（未知/高阻）、红=E（冲突/多驱动）。
 * 导线变红 = 该网络有多个互相打架的驱动源，或接了值不合法的引脚。
 *
 * 用法：
 *   java -cp logisim.exe;classes WireValues in.circ 电路名 [combo]
 *   combo 是 DipSwitch 的原始值位串（"000" 表示全朝上 = 逻辑 1），
 *   从左到右 = 开关从上到下（与 SimTable 打印的位串一致）；省略则全 0。
 */
public class WireValues {
    public static void main(String[] a) {
        try {
            run(a);
        } catch (Throwable t) {
            t.printStackTrace();
            System.exit(1);
        }
        System.exit(0);
    }

    static void run(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: WireValues <circ> <circuit> [combo]");
            System.exit(2);
        }
        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile f = loader.openLogisimFile(new File(args[0]));
        Project proj = new Project(f);
        Circuit circ = f.getCircuit(args[1]);
        if (circ == null) {
            System.err.println("no circuit " + args[1]);
            System.exit(3);
        }
        String combo = args.length > 2 ? args[2] : "";

        List<Component> dips = new ArrayList<>();
        for (Component c : circ.getNonWires()) {
            if ("DipSwitch".equals(c.getFactory().getName())) dips.add(c);
        }
        dips.sort(Comparator.comparingInt((Component c) -> c.getLocation().getY())
                .thenComparingInt(c -> c.getLocation().getX()));

        CircuitState st = new CircuitState(proj, circ);
        st.getPropagator().propagate();
        for (int i = 0; i < dips.size(); i++) {
            // combo 从左到右 = 开关从上到下（与 SimTable 打印的位串一致）
            int bit = i < combo.length() ? combo.charAt(i) - '0' : 0;
            Object data = st.getInstanceState(dips.get(i)).getData();
            java.lang.reflect.Field fd = data.getClass().getDeclaredField("vals");
            fd.setAccessible(true);
            Value[] vals = (Value[]) fd.get(data);
            vals[0] = Value.createKnown(BitWidth.create(1), bit);
            st.markComponentAsDirty(dips.get(i));
        }
        st.getPropagator().propagate();

        int err = 0, x = 0, one = 0, zero = 0;
        for (Wire w : circ.getWires()) {
            Value v = st.getValue(w.getEnd0());
            String s = v == null ? "null" : v.toDisplayString();
            String tag = "";
            if (v != null && v.isErrorValue()) {
                tag = "   <<< E（红：多驱动/冲突）";
                err++;
            } else if (v == null || v.isUnknown()) {
                tag = "   <<< x（蓝：未驱动/高阻）";
                x++;
            } else if (v == Value.TRUE) {
                one++;
            } else {
                zero++;
            }
            System.out.printf("%-14s -> %-14s %-4s%s%n",
                    w.getEnd0(), w.getEnd1(), s, tag);
        }
        System.out.printf("%n合计：绿(1)=%d 深绿(0)=%d 蓝(x)=%d 红(E)=%d%n", one, zero, x, err);
        System.out.print("开关原始值：" + combo + "（0=扳手朝上=逻辑1，1=朝下=逻辑0）");
        if (dips.isEmpty()) System.out.print("  [无 DipSwitch]");
        System.out.println();
        System.out.flush();
    }
}
