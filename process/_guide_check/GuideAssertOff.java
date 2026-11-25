// Verifies doc claim (section 21): assert is DISABLED by default, enabled with -ea.
public class GuideAssertOff {
    public static void main(String[] args) {
        assert false : "should only fire with -ea";
        System.out.println("ASSERT-SKIPPED");
    }
}