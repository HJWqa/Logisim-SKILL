import java.io.File;

import com.cburch.logisim.comp.ComponentFactory;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.tools.AddTool;
import com.cburch.logisim.tools.Library;
import com.cburch.logisim.tools.Tool;

/**
 * 打印元件的属性名和默认值，用来手写 .circ。
 * 用法：java -cp logisim.jar;classes FactoryDump in.circ [元件名…]
 */
public class FactoryDump {
    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile file = loader.openLogisimFile(new File(args[0]));
        for (Library lib : file.getLibraries()) {
            for (Tool t : lib.getTools()) {
                if (!(t instanceof AddTool)) continue;
                ComponentFactory f = ((AddTool) t).getFactory();
                if (args.length > 1) {
                    boolean want = false;
                    for (int i = 1; i < args.length; i++)
                        if (f.getName().equals(args[i])) want = true;
                    if (!want) continue;
                }
                AttributeSet as = f.createAttributeSet();
                System.out.println("=== " + f.getName() + "  lib=" + lib.getName());
                for (Attribute<?> a : as.getAttributes()) {
                    System.out.println("    " + a.getName() + " = " + as.getValue(a));
                }
            }
        }
        System.out.flush();
        System.exit(0);
    }
}
