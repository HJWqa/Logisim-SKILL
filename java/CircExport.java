import java.awt.Color;
import java.awt.Component;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.Panel;
import java.awt.image.BufferedImage;
import java.io.File;

import javax.imageio.ImageIO;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.ComponentDrawContext;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;

/**
 * 用 Logisim 自己的渲染引擎把 .circ 里的电路导出成 PNG。
 *
 * 走的是 Logisim「文件 → 导出图像」的同一段代码：
 *   Circuit.getBounds() 取包围盒 → 建 BufferedImage → Graphics2D 缩放/平移
 *   → ComponentDrawContext(printerView=true) → Circuit.draw()
 * printerView=true 是"打印视图"，导线和元件都用黑色画，不会出现仿真着的蓝/绿线。
 *
 * 用法：
 *   java -Djava.awt.headless=true -cp logisim.jar;classes CircExport in.circ 半加器 out.png 4
 *   java ... CircExport in.circ ALL outdir 4
 */
public class CircExport {
    public static void main(String[] args) throws Exception {
        if (args.length < 4) {
            System.err.println("usage: CircExport <circ> <circuit|ALL> <out.png|outdir> <scale>");
            System.exit(2);
        }
        String src = args[0];
        String which = args[1];
        String dst = args[2];
        double scale = Double.parseDouble(args[3]);

        Component dummy = new Panel();
        Loader loader = new Loader(dummy);
        LogisimFile file = loader.openLogisimFile(new File(src));
        Project proj = new Project(file);

        boolean all = which.equalsIgnoreCase("ALL");
        Circuit only = all ? null : file.getCircuit(which);
        if (!all && only == null) {
            System.err.println("no such circuit: " + which);
            for (Circuit c : file.getCircuits()) {
                System.err.println("  have: " + c.getName());
            }
            System.exit(3);
        }

        File outDir = new File(dst);
        if (all && !outDir.isDirectory()) {
            outDir.mkdirs();
        }

        for (Circuit circ : file.getCircuits()) {
            if (!all && circ != only) {
                continue;
            }
            // 空白画布的 Graphics 只用来量尺寸（字体度量）
            BufferedImage probe = new BufferedImage(8, 8, BufferedImage.TYPE_INT_RGB);
            Graphics pg = probe.getGraphics();
            Bounds b = circ.getBounds(pg).expand(10);
            pg.dispose();

            int w = (int) Math.round(b.getWidth() * scale);
            int h = (int) Math.round(b.getHeight() * scale);
            BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
            Graphics g2 = img.getGraphics();
            g2.setColor(Color.WHITE);
            g2.fillRect(0, 0, w, h);
            g2.setColor(Color.BLACK);

            Graphics2D gg = (Graphics2D) g2.create();
            gg.scale(scale, scale);
            gg.translate(-b.getX(), -b.getY());

            CircuitState state = proj.getCircuitState(circ);
            // 先按默认输入（全 0）传播一次，电源脚才能显示出 1
            proj.getSimulator().setCircuitState(state);
            proj.getSimulator().step();
            ComponentDrawContext ctx = new ComponentDrawContext(
                    dummy, circ, state, g2, gg, true);
            circ.draw(ctx, null);
            gg.dispose();
            g2.dispose();

            File target;
            if (all || outDir.isDirectory()) {
                target = new File(outDir, circ.getName() + ".png");
            } else {
                target = outDir;
            }
            ImageIO.write(img, "png", target);
            System.out.printf("%s  %dx%d  -> %s%n",
                    circ.getName(), w, h, target.getPath());
        }
        System.out.flush();
        System.exit(0);   // AWT 线程不退出的话 JVM 会一直挂着
    }
}
