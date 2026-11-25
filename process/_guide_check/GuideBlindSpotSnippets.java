import java.io.*;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import java.util.stream.Collectors;

// Compile-and-run verification for newly added snippets in JAVA_GENERAL_GUIDE.md
// (sections 3.4, 4.6, 7.2, 11.5, 13.2 fix, 16.4, 18.2, 19.5, 21, 25.5).
// Intentional compile-error lines from the doc are NOT included here.
public class GuideBlindSpotSnippets {

    // ---- 3.4 annotations ----
    @FunctionalInterface
    interface Task { void run(); }

    static class Base {
        @Override
        public String toString() { return "base"; }
    }

    // ---- 3.4 varargs ----
    static int sum(int... nums) {
        int total = 0;
        for (int n : nums) total += n;
        return total;
    }

    // ---- 7.2 blank final assigned in constructor ----
    static class Account {
        private final String owner;
        Account(String owner) { this.owner = owner; }
        String getOwner() { return owner; }
    }

    // ---- 11.5 / 13.2 ----
    static class User {
        private final String name;
        private final int age;
        private final String dept;
        User(String name) { this(name, 0, "none"); }
        User(String name, int age, String dept) { this.name = name; this.age = age; this.dept = dept; }
        String getName() { return name; }
        int getAge() { return age; }
        String getDept() { return dept; }
    }

    // ---- 18.2 serialization + transient ----
    static class Session implements Serializable {
        String token = "t-1";
        transient String password = "secret";
    }

    public static void main(String[] args) throws Exception {
        // 3.4 varargs
        check(sum() == 0, "varargs zero");
        check(sum(1, 2, 3) == 6, "varargs three");
        String name = "tom";
        check(String.format("%s-%d", name, 42).equals("tom-42"), "format varargs");
        Task t = () -> {};
        t.run();

        // 4.6 boxing
        Integer boxed = 42;
        int unboxed = boxed;
        List<Integer> list = new ArrayList<>();
        list.add(1);
        int x = list.get(0);
        check(unboxed == 42 && x == 1, "boxing roundtrip");
        Integer a127 = 127, b127 = 127, a128 = 128, b128 = 128;
        check(a127 == b127, "Integer cache 127 same ref");
        check(!(a128 == b128), "Integer cache 128 different ref");
        try {
            Integer n = null;
            int bad = n;
            check(false, "unbox null should NPE");
        } catch (NullPointerException expected) { }

        // 7.2 final semantics
        final int fx = 10;
        final List<String> flist = new ArrayList<>();
        flist.add("a");                       // legal: content mutable
        check(flist.size() == 1 && fx == 10, "final reference vs content");
        check(new Account("alice").getOwner().equals("alice"), "blank final in ctor");

        // 11.5 comparators
        List<String> names = new ArrayList<>(Arrays.asList("b", "a", "c"));
        names.sort(Comparator.naturalOrder());
        check(names.get(0).equals("a"), "naturalOrder");
        List<User> users = new ArrayList<>(Arrays.asList(
                new User("u1", 30, "ops"), new User("u2", 20, "ops"), new User("u3", 25, "dev")));
        users.sort(Comparator.comparing(User::getAge));
        check(users.get(0).getAge() == 20, "comparing age");
        users.sort(Comparator.comparing(User::getDept).thenComparing(User::getAge).reversed());
        check(users.get(0).getDept().equals("ops") && users.get(0).getAge() == 30, "thenComparing reversed");
        try {
            TreeSet<Object> noRule = new TreeSet<>();
            noRule.add(new Object());
            noRule.add(new Object());
            check(false, "TreeSet without Comparable should CCE");
        } catch (ClassCastException expected) { }

        // 13.2 method references (fixed lines)
        List<User> us = names.stream().map(User::new).collect(Collectors.toList());
        check(us.get(0).getName().equals("a"), "ctor reference User::new");
        Function<String, Integer> f = Integer::parseInt;
        check(f.apply("42") == 42, "static method ref");
        Function<String, Integer> len = String::length;
        check(len.apply("abc") == 3, "String::length ref");

        // 16.4 BigDecimal
        BigDecimal ba = new BigDecimal("0.1");
        BigDecimal bb = new BigDecimal("0.2");
        BigDecimal bsum = ba.add(bb);
        check(bsum.compareTo(new BigDecimal("0.3")) == 0, "BigDecimal 0.1+0.2==0.3");
        BigDecimal avg = bsum.divide(new BigDecimal("3"), 2, RoundingMode.HALF_UP);
        check(avg.compareTo(new BigDecimal("0.10")) == 0, "divide scale rounding");
        check(ba.compareTo(bb) < 0, "compareTo");
        check(!new BigDecimal("1.0").equals(new BigDecimal("1.00")), "equals compares scale");
        try {
            new BigDecimal("1").divide(new BigDecimal("3"));
            check(false, "divide without scale should throw");
        } catch (ArithmeticException expected) { }

        // 18.2 serialization + transient
        Session s = new Session();
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (ObjectOutputStream oos = new ObjectOutputStream(bos)) { oos.writeObject(s); }
        Session back;
        try (ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(bos.toByteArray()))) {
            back = (Session) ois.readObject();
        }
        check(back.token.equals("t-1") && back.password == null, "transient skipped");

        // 19.5 atomic via CAS
        AtomicInteger counter = new AtomicInteger();
        check(counter.incrementAndGet() == 1, "AtomicInteger CAS");

        // 21 assert (run with -ea)
        int positive = 1;
        assert positive > 0 : "must be positive";

        System.out.println("ALL CHECKS PASSED");
    }

    static void check(boolean cond, String label) {
        if (!cond) throw new AssertionError("FAILED: " + label);
    }
}