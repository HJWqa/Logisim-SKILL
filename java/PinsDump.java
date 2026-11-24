import java.awt.Graphics;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.List;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.StdAttr;

/**
 * 把 .circ 的几何整体导出成 TSV，供 Python 做连通性/真值表/版面审计。
 *
 * 为什么不硬编码几何：同一个 "NAND Gate" 在 size/输入数不同时引脚位置就不同
 * （size=30 时 AND 的输入在 x-30、NAND 在 x-40；n=2 时 dy=±10、n>=3 时步长 10），
 * 只有 Logisim 自己算出来的坐标才是真的。
 *
 * 用法：java -Djava.awt.headless=true -cp logisim.exe;classes PinsDump in.circ [out.tsv]
 *
 * 输出（TSV，字段以 \t 分隔）：
 *   CIRC  <name> <bx> <by> <bw> <bh>
 *   COMP  <factory> <idx> <x> <y> <bx> <by> <bw> <bh> <label>
 *   ATTR  <compIdx> <name> <value>
 *   END   <compIdx> <pinIdx> <x> <y> <IN|OUT|INOUT>
 *   WIRE  <x1> <y1> <x2> <y2>
 */
public class PinsDump {
    /** 只导出这些属性，避免整份 AttributeSet 刷屏。 */
    private static final String[] WANT = {
        "label", "output", "inputs", "size", "facing", "pull", "tristate",
        "width", "value", "select", "NSwitches", "active", "text"
    };

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: PinsDump <circ> [out.tsv]");
            System.exit(2);
        }
        java.io.PrintStream out = System.out;
        if (args.length > 1) {
            out = new java.io.PrintStream(args[1], "UTF-8");
        }

        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile file = loader.openLogisimFile(new File(args[0]));
        BufferedImage probe = new BufferedImage(8, 8, BufferedImage.TYPE_INT_RGB);
        Graphics g = probe.getGraphics();

        for (Circuit circ : file.getCircuits()) {
            Bounds cb = circ.getBounds(g);
            out.printf("CIRC\t%s\t%d\t%d\t%d\t%d%n",
                    circ.getName(), cb.getX(), cb.getY(), cb.getWidth(), cb.getHeight());

            int idx = 0;
            for (Component c : circ.getNonWires()) {
                Object label = c.getAttributeSet().getValue(StdAttr.LABEL);
                String lab = label == null ? "" : label.toString();
                Bounds b = c.getBounds(g);
                out.printf("COMP\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s%n",
                        esc(c.getFactory().getName()), idx, c.getLocation().getX(),
                        c.getLocation().getY(), b.getX(), b.getY(), b.getWidth(),
                        b.getHeight(), esc(lab));

                AttributeSet as = c.getAttributeSet();
                for (Attribute<?> a : as.getAttributes()) {
                    String an = a.getName();
                    boolean want = false;
                    for (String w : WANT) {
                        if (w.equals(an)) { want = true; break; }
                    }
                    if (!want) continue;
                    Object v = as.getValue(a);
                    out.printf("ATTR\t%d\t%s\t%s%n", idx, esc(an), esc(String.valueOf(v)));
                }

                List<EndData> ends = c.getEnds();
                for (int i = 0; i < ends.size(); i++) {
                    EndData e = ends.get(i);
                    Location l = e.getLocation();
                    String dir = e.isInput() ? "IN" : e.isOutput() ? "OUT" : "INOUT";
                    out.printf("END\t%d\t%d\t%d\t%d\t%s%n", idx, i,
                            l.getX(), l.getY(), dir);
                }
                idx++;
            }
            for (Wire w : circ.getWires()) {
                out.printf("WIRE\t%d\t%d\t%d\t%d%n",
                        w.getEnd0().getX(), w.getEnd0().getY(),
                        w.getEnd1().getX(), w.getEnd1().getY());
            }
        }
        out.flush();
        System.exit(0);
    }

    private static String esc(String s) {
        return s.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ');
    }
}
