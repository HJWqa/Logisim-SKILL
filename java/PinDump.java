import java.io.File;
import java.util.List;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.StdAttr;

/**
 * 打印 .circ 里每个元件的类型、位置和引脚坐标。
 *
 * 用来确定 Logisim 各库元件（尤其 TTL 74LS00/74LS86）的引脚几何，
 * 手写导线坐标时先查表，别再靠猜。
 *
 * 用法：java -cp logisim.jar;classes PinDump in.circ [circuit]
 */
public class PinDump {
    public static void main(String[] args) throws Exception {
        String src = args[0];
        String which = args.length > 1 ? args[1] : null;

        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile file = loader.openLogisimFile(new File(src));
        for (Circuit circ : file.getCircuits()) {
            if (which != null && !circ.getName().equals(which)) {
                continue;
            }
            System.out.println("=== " + circ.getName() + "  bounds=" + circ.getBounds());
            for (Component c : circ.getNonWires()) {
                Object label = c.getAttributeSet().getValue(StdAttr.LABEL);
                System.out.printf("  %-12s loc=%-10s %s%n",
                        c.getFactory().getName(), c.getLocation(),
                        label == null || label.toString().isEmpty() ? "" : "label=" + label);
                List<EndData> ends = c.getEnds();
                for (int i = 0; i < ends.size(); i++) {
                    EndData e = ends.get(i);
                    Location l = e.getLocation();
                    System.out.printf("      pin %2d  %-10s %s%n", i, l,
                            e.isInput() ? "IN" : e.isOutput() ? "OUT" : "INOUT");
                }
            }
        }
        System.out.flush();
        System.exit(0);
    }
}
