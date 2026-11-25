import java.util.ArrayList;
import java.util.List;

// Negative test: these lines are documented as COMPILE ERRORS in section 7.2.
// javac MUST reject this file; success here would falsify the doc.
public class GuideFinalNegative {
    public static void main(String[] args) {
        final int x = 10;
        x = 20;                            // doc: cannot assign a value to final variable x

        final List<String> list = new ArrayList<>();
        list = new ArrayList<>();          // doc: cannot reassign final reference
    }
}