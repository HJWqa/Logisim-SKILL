import java.awt.Component;
import java.awt.Panel;
import java.io.File;

import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.file.ToolbarData;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.tools.Tool;

/** 打印 .circ 工程顶部工具栏里的工具，确认 `<toolbar>` 被正确读入。 */
public class ToolbarDump {
    public static void main(String[] args) throws Exception {
        Component dummy = new Panel();
        Loader loader = new Loader(dummy);
        LogisimFile file = loader.openLogisimFile(new File(args[0]));
        Project proj = new Project(file);
        ToolbarData bar = proj.getOptions().getToolbarData();
        System.out.println("toolbar size: " + bar.size());
        for (int i = 0; i < bar.size(); i++) {
            Object o = bar.get(i);
            if (o instanceof Tool) {
                System.out.println("  " + ((Tool) o).getName());
            } else {
                System.out.println("  <sep>");
            }
        }
        System.exit(0);
    }
}
