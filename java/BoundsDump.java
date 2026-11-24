import java.io.File;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.StdAttr;

/**
 * 打印 .circ 里每个元件的外接矩形（用于检查导线有没有穿过元件本体）。
 * 用法：java -cp logisim.jar;classes BoundsDump in.circ [circuit]
 */
public class BoundsDump {
    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile file = loader.openLogisimFile(new File(args[0]));
        String which = args.length > 1 ? args[1] : null;
        java.awt.image.BufferedImage probe =
                new java.awt.image.BufferedImage(8, 8, java.awt.image.BufferedImage.TYPE_INT_RGB);
        java.awt.Graphics g = probe.getGraphics();
        for (Circuit circ : file.getCircuits()) {
            if (which != null && !circ.getName().equals(which)) {
                continue;
            }
            System.out.println("=== " + circ.getName() + "  bounds=" + circ.getBounds(g));
            for (Component c : circ.getNonWires()) {
                Object label = c.getAttributeSet().getValue(StdAttr.LABEL);
                System.out.printf("  %-12s loc=%-10s bounds=%-28s %s%n",
                        c.getFactory().getName(), c.getLocation(), c.getBounds(g),
                        label == null || label.toString().isEmpty() ? "" : "label=" + label);
            }
        }
        System.out.flush();
        System.exit(0);
    }
}
