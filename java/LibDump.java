import java.io.File;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.tools.AddTool;
import com.cburch.logisim.tools.Library;
import com.cburch.logisim.tools.Tool;

/**
 * 列出 .circ 里各元件库的工具（元件）名，用来确认某个元件在 XML 里怎么写。
 * 用法：java -cp logisim.jar;classes LibDump in.circ
 */
public class LibDump {
    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(new java.awt.Panel());
        LogisimFile file = loader.openLogisimFile(new File(args[0]));
        for (Library lib : file.getLibraries()) {
            System.out.println("=== " + lib.getName());
            for (Tool t : lib.getTools()) {
                String factory = "";
                if (t instanceof AddTool) {
                    factory = "  factory=" + ((AddTool) t).getFactory().getName();
                }
                System.out.println("    " + t.getName() + factory);
            }
        }
        System.out.flush();
        System.exit(0);
    }
}
