import java.io.*;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;
import java.util.stream.*;

/** Harness: every runnable snippet quoted in guide_file/JAVA_GUIDE.md must compile under JDK 1.8. */
@SuppressWarnings("unused")
public class GuideSnippets {

    // ---- section 4.1 / 4.2 / 4.3 ----
    public static class User {
        private final String displayName;
        private static int instanceCount = 0;

        public User(String displayName) {
            this.displayName = displayName;
            instanceCount++;
        }

        public User() { this("anonymous"); }

        public String getDisplayName() { return displayName; }
        public static int getInstanceCount() { return instanceCount; }
        public int getAge() { return 0; }
        public String getName() { return displayName; }

        @Override
        public String toString() { return "User(" + displayName + ")"; }
    }

    public static class AdminUser extends User {
        public AdminUser(String name) { super(name); }

        @Override
        public String toString() { return "Admin" + super.toString(); }
    }

    // ---- section 4.5 enum ----
    public enum FaultStatus {
        PENDING("pending"),
        DONE("done");

        private final String value;
        FaultStatus(String value) { this.value = value; }
        public String getValue() { return value; }
        public static FaultStatus fromValue(String v) {
            for (FaultStatus s : values()) {
                if (s.value.equals(v)) return s;
            }
            throw new IllegalArgumentException(v);
        }
    }

    // ---- section 5.3 custom exception ----
    public static class BusinessException extends RuntimeException {
        private final String code;
        public BusinessException(String code, String msg) {
            super(msg);
            this.code = code;
        }
        public String getCode() { return code; }
    }

    static void log(String fmt, Object... args) { }

    // ---- section 3.1 / 3.2 / 3.4 / 3.5 ----
    public static void basics() {
        int count = 42;
        long big = 100_000L;
        double ratio = 3.14;
        float f = 1.5f;
        char c = 'A';
        boolean ok = true;
        String s = "hello";

        int a = 7, b = 2;
        double r1 = a / b;
        double r2 = (double) a / b;
        int back = (int) 3.99;
        long auto = a;
        String num = "42";
        int parsed = Integer.parseInt(num);
        String str = String.valueOf(42);

        if (count > 0) { log("a"); } else if (count == 0) { log("b"); } else { log("c"); }
        for (int i = 0; i < 10; i++) { log("loop"); }
        List<String> names = new ArrayList<>();
        for (String name : names) { log(name); }
        int code = 1;
        switch (code) {
            case 1: break;
            case 2:
            case 3: break;
            default: break;
        }

        int[] arr = new int[5];
        int[] nums = {3, 1, 4, 1, 5};
        Arrays.sort(nums);
        Arrays.toString(nums);
        int[] copy = Arrays.copyOf(nums, 10);
        int[][] matrix = new int[3][4];
        BigInteger bd = new BigInteger("123456789012345678901234567890");
    }

    // ---- section 5.1 exceptions ----
    public static void exceptions(File f) throws IOException {
        try {
            String line = Files.readAllLines(Paths.get("in.txt")).get(0);
            int x = Integer.parseInt(line);
        } catch (NumberFormatException e) {
            log("bad number", e);
        } catch (IOException | RuntimeException e) {
            throw new IllegalStateException("wrap", e);
        } finally {
            log("cleanup");
        }

        try (FileInputStream in = new FileInputStream(f)) {
            in.read();
        }
    }

    // ---- section 6 collections ----
    public static void collections() {
        List<String> box = new ArrayList<>();
        box.add("ok");
        String s = box.get(0);
        List<int[]> mm = new ArrayList<>();

        List<String> names = new ArrayList<>();
        names.add("tom");
        names.get(0);
        names.remove(0);
        Map<String, Integer> age = new HashMap<>();
        age.put("tom", 18);
        age.getOrDefault("bob", 0);
        for (Map.Entry<String, Integer> e : age.entrySet()) { log(e.getKey()); }
        names.sort(Comparator.naturalOrder());
        age.putIfAbsent("x", 1);
        age.computeIfAbsent("y", k -> new Random().nextInt());

        Collection<?> wildcardRead = names;
        printAll(names);
        List<Integer> ints = new ArrayList<>();
        log(String.valueOf(sumAll(ints)));

        List<String> empty = Collections.emptyList();
        List<String> unmod = Collections.unmodifiableList(new ArrayList<>(names));
    }

    static void printAll(List<?> list) { }
    static double sumAll(List<? extends Number> list) { return 0; }

    // ---- section 7 lambda / stream / optional ----
    public static void functional(List<User> users) {
        Runnable r = () -> System.out.println("hi");
        Function<String, Integer> len = s -> s.length();
        BiFunction<Integer, Integer, Integer> add = (x, y) -> x + y;
        Predicate<String> notEmpty = s -> !s.isEmpty();

        List<String> result = users.stream()
                .filter(u -> u.getAge() >= 18)
                .sorted(Comparator.comparing(User::getAge).reversed())
                .map(User::getName)
                .distinct()
                .limit(10)
                .collect(Collectors.toList());

        boolean any = users.stream().anyMatch(u -> u.getAge() > 60);
        long cnt = users.stream().filter(u -> !u.getName().isEmpty()).count();
        long total = users.stream().mapToLong(u -> u.getAge()).sum();
        String joined = users.stream().map(User::getName).collect(Collectors.joining(", "));
        Map<Integer, List<User>> grouped = users.stream().collect(Collectors.groupingBy(User::getAge));
        Map<String, Integer> byName = users.stream().collect(Collectors.toMap(User::getName, User::getAge));

        Optional<User> u = Optional.of(new User());
        String name = u.map(User::getName).orElse("anonymous");
        u.ifPresent(x -> log("{}", x));
        User orThrow = u.orElseThrow(() -> new BusinessException("NF", "missing"));
        Integer viaIntStream = IntStream.range(0, 10).map(i -> i * 2).boxed().findFirst().orElse(null);
    }

    // ---- section 8 strings & IO ----
    public static void strings(List<String> parts, String s) throws IOException {
        int n = s.length();
        char first = s.charAt(0);
        String mid = s.substring(1, 3);
        boolean has = s.contains("x");
        String[] sp = s.split(",");
        String[] dotted = "a.b.c".split("\\.");
        String joined = String.join(",", parts);
        String stripped = s.trim();
        String lower = s.toLowerCase(Locale.ROOT);
        boolean starts = s.startsWith("h");
        String fmt = String.format("%s-%s", "a", "b");
        String rep = s.replaceAll("\\d", "#");

        StringBuilder sb = new StringBuilder();
        for (String p : parts) { sb.append(p).append(','); }
        String out = sb.toString();

        List<String> lines = Files.readAllLines(Paths.get("data.txt"), StandardCharsets.UTF_8);
        Files.write(Paths.get("out.txt"), "done\n".getBytes(StandardCharsets.UTF_8));
        boolean exists = Files.exists(Paths.get("data.txt"));
        boolean isDir = Files.isDirectory(Paths.get("data.txt"));
        Path resolved = Paths.get("base").resolve("sub");
        try (Stream<String> stream = Files.lines(Paths.get("big.txt"))) {
            stream.filter(l -> !l.isEmpty()).forEach(GuideSnippets::logStatic);
        }
    }

    static void handle(String line) { }
    static void logStatic(String line) { }

    // ---- section 9 concurrency ----
    public static void concurrency() throws Exception {
        Thread t = new Thread(() -> System.out.println("working in " + Thread.currentThread().getName()));
        t.start();
        t.join();

        ExecutorService pool = Executors.newFixedThreadPool(4);
        Future<Integer> fut = pool.submit(() -> heavyCompute());
        Integer result = fut.get(3, TimeUnit.SECONDS);
        pool.shutdown();

        Counter c = new Counter();
        c.inc();
        BlockingQueue<String> q = new ArrayBlockingQueue<>(10);
        q.put("x");
        String head = q.poll(1, TimeUnit.SECONDS);
        ConcurrentHashMap<String, Integer> chm = new ConcurrentHashMap<>();
        chm.computeIfAbsent("k", k -> 0);
        java.util.concurrent.atomic.AtomicInteger ai = new java.util.concurrent.atomic.AtomicInteger();
        ai.incrementAndGet();
    }

    static int heavyCompute() { return 42; }

    public static class Counter {
        private int n;
        public synchronized void inc() { n++; }
    }

    public static void main(String[] args) { }
}
