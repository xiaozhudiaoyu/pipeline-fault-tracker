import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;
import java.util.regex.*;
import java.util.stream.*;

/** Harness: runnable Java 8 snippets from guide_file/JAVA_GENERAL_GUIDE.md must compile under JDK 1.8. */
@SuppressWarnings("unused")
public class GeneralGuideSnippets {

    // ---- sections 4 / 5 / 6 ----
    public static void basics() {
        int i = 7, n = 10;
        long big = 100_000L;
        float f = 1.5f;
        char c = 'A';
        boolean ok = true;
        String s = "hello";

        long autoWiden = i;
        int back = (int) 3.99;
        double r = (double) 7 / 2;
        int parsed = Integer.parseInt("42");
        double d = Double.parseDouble("3.14");
        String s1 = String.valueOf(42);
        long t = 5L * Integer.MAX_VALUE;
        long safe = Math.multiplyExact(big, 100_000L);

        char grade;
        int score = 70;
        if (score >= 90)      { grade = 'A'; }
        else if (score >= 60) { grade = 'B'; }
        else                  { grade = 'C'; }

        Deque<Integer> queue = new ArrayDeque<>();
        while (queue.peek() != null) { queue.poll(); }
        boolean success = false;
        int attempt = 0;
        do { attempt++; } while (attempt < 3 && !success);

        for (int k = 0; k < n; k++) { GeneralGuideSnippets.work(k); }
        List<String> names = new ArrayList<>();
        for (String name : names) { System.out.println(name); }

        int m = 2, p = 2;
        outer:
        for (int x = 0; x < m; x++)
            for (int y = 0; y < p; y++)
                if (hit(x, y)) break outer;

        int day = 2;
        switch (day) {
            case 1: case 2: case 3:
                meeting(); break;
            case 4:
                report(); break;
            default:
                rest();
        }

        int[] arr = new int[5];
        int[] nums = {3, 1, 4, 1, 5};
        int len = nums.length;
        nums[0] = 9;
        nums[4] = 9;
        Arrays.sort(nums);
        Arrays.toString(nums);
        Arrays.fill(arr, -1);
        int[] a2 = {1};
        Arrays.equals(nums, a2);
        int[] grown = Arrays.copyOf(nums, 10);
        int[][] grid = new int[3][4];
    }

    static void work(int k) { }
    static boolean hit(int i, int j) { return false; }
    static void meeting() { }
    static void report() { }
    static void rest() { }

    // ---- section 7 ----
    public static class User {
        private String name;
        private int age;
        private static int count = 0;

        public User(String name) {
            this(name, 0);
            this.name = name;
        }

        public User(String name, int age) {
            this.name = name;
            this.age = age;
            count++;
        }

        public String getName() { return name; }
        public void setName(String name) { this.name = name; }
        public int getAge() { return age; }
        public String getDept() { return "d"; }
        public boolean isAdult() { return age >= 18; }
        public static int getCount() { return count; }

        @Override
        public String toString() { return "User(name=" + name + ", age=" + age + ")"; }
    }

    static { /* static block */ }
    { /* instance init block */ }

    // ---- section 8 ----
    public interface Payable {
        BigDecimal pay(BigDecimal amount);
        default boolean supportsRefund() { return true; }
    }

    public static class AdminUser extends User implements Payable {
        private final String dept;

        public AdminUser(String name, String dept) {
            super(name);
            this.dept = dept;
        }

        @Override
        public String toString() { return "Admin" + super.toString(); }

        @Override
        public BigDecimal pay(BigDecimal amount) { return amount; }
    }

    public static void polymorphism() {
        User u = new AdminUser("Bob", "ops");
        String s = u.toString();
        AdminUser a = (AdminUser) u;
        if (u instanceof AdminUser) {
            AdminUser safe = (AdminUser) u;
        }
    }

    // ---- section 9 ----
    public enum OrderStatus {
        PENDING("pending", false),
        PAID("paid", true),
        CLOSED("closed", true);

        private final String code;
        private final boolean finalState;

        OrderStatus(String code, boolean finalState) {
            this.code = code;
            this.finalState = finalState;
        }

        public String getCode() { return code; }
        public boolean isFinalState() { return finalState; }

        public static OrderStatus fromCode(String code) {
            for (OrderStatus s : values()) {
                if (s.code.equals(code)) return s;
            }
            throw new IllegalArgumentException("Unknown code: " + code);
        }
    }

    static void enumExtras() {
        OrderStatus s = OrderStatus.PAID;
        String name = s.name();
        int ordinal = s.ordinal();
        OrderStatus same = OrderStatus.valueOf("PAID");
        switch (s) {
            case PENDING: break;
            default: break;
        }
    }

    static void anonymousClass() {
        Runnable r1 = new Runnable() {
            @Override public void run() { System.out.println("hi"); }
        };
    }

    // ---- section 10 ----
    static String readFirstLine(String p) throws IOException { return "1"; }
    static void handle(int n) { }
    static void release() { }

    public static void exceptions(File f) throws IOException {
        try {
            String line = readFirstLine("in.txt");
            int n = Integer.parseInt(line);
            handle(n);
        } catch (NumberFormatException e) {
            log("bad number", e);
        } catch (IOException | RuntimeException e) {
            throw new IllegalStateException("wrap", e);
        } finally {
            release();
        }

        try (FileInputStream in = new FileInputStream(f)) {
            in.read();
        }
    }

    static void log(String msg, Throwable t) { }

    // ---- section 11 ----
    public static void collections() {
        List<String> names = new ArrayList<>();
        names.add("tom");
        names.add(0, "first");
        names.get(0);
        names.remove("tom");
        names.remove(0);
        names.set(0, "jerry");
        names.size();
        names.isEmpty();
        names.contains("x");

        Map<String, Integer> ages = new HashMap<>();
        ages.put("tom", 18);
        ages.get("bob");
        ages.getOrDefault("bob", 0);
        ages.putIfAbsent("bob", 20);
        ages.computeIfAbsent("bob", k -> 0);
        Map<String, List<String>> groups = new HashMap<>();
        groups.computeIfAbsent("group1", k -> new ArrayList<>()).add("x");
        for (Map.Entry<String, Integer> e : ages.entrySet()) { log(e.getKey(), null); }
        for (String k : ages.keySet()) { log(k, null); }

        names.sort(Comparator.naturalOrder());
        Collections.unmodifiableList(names);
        List<String> fixed = new ArrayList<>(Arrays.asList("a", "b"));

        names.removeIf(n -> n.isEmpty());
        Iterator<String> it = names.iterator();
        while (it.hasNext()) { if (bad(it.next())) it.remove(); }

        LinkedList<String> ll = new LinkedList<>();
        TreeSet<String> ts = new TreeSet<>();
        LinkedHashSet<String> lhs = new LinkedHashSet<>();
        TreeMap<String, String> tm = new TreeMap<>();
        ts.first(); ts.pollFirst();
        Vector<String> v = new Vector<>();
        Hashtable<String, String> h = new Hashtable<>();
        Stack<String> st = new Stack<>();
        Collections.synchronizedList(new ArrayList<String>());
    }

    static boolean bad(String s) { return false; }

    // ---- section 12 ----
    public static class Pair<A, B> {
        private final A first;
        private final B second;
        Pair(A first, B second) { this.first = first; this.second = second; }
        A getFirst() { return first; }
    }

    static void printAll(List<?> list) { }
    static double sumAll(List<? extends Number> list) { return 0; }
    static void fill(List<? super Integer> list) { list.add(1); }
    static <T> List<T> repeat(T item, int n) {
        List<T> out = new ArrayList<>();
        for (int i = 0; i < n; i++) out.add(item);
        return out;
    }

    static void generics() {
        List<String> box = new ArrayList<>();
        box.add("ok");
        String s = box.get(0);
        Map<String, List<Integer>> index = new HashMap<>();
        Pair<String, Integer> p = new Pair<>("a", 1);
        List<int[]> arrayOfIntArrays = new ArrayList<>();
    }

    // ---- section 13 ----
    public static void lambdas(List<String> names, List<User> users) {
        Runnable r2 = () -> System.out.println("hi");
        BiFunction<Integer, Integer, Integer> add = (x, y) -> x + y;
        Function<String, String> upper = (String str) -> {
            String t = str.trim();
            return t.toUpperCase();
        };
        Function<String, String> dbl = x -> x + x;

        names.forEach(System.out::println);
        users.sort(Comparator.comparing(User::getAge));
        List<User> us = names.stream().map(User::new).collect(Collectors.toList());
        Function<String, Integer> fi = Integer::parseInt;

        AtomicInteger state = new AtomicInteger();
        names.forEach(n -> state.addAndGet(n.length()));   // effectively-final capture via atomic
    }

    static class AtomicInteger { int v; void addAndGet(int d) { v += d; } }

    // ---- section 14 ----
    public static void streams(List<User> users) {
        List<String> result = users.stream()
                .filter(u -> u.getAge() >= 18)
                .sorted(Comparator.comparing(User::getName))
                .map(User::getName)
                .distinct()
                .limit(10)
                .collect(Collectors.toList());

        Optional<User> max = users.stream().max(Comparator.comparing(User::getAge));
        long cnt = users.stream().count();
        boolean any = users.stream().anyMatch(u -> u.getAge() > 60);
        boolean all = users.stream().allMatch(User::isAdult);
        boolean none = users.stream().noneMatch(User::isAdult);
        Optional<User> first = users.stream().findFirst();
        int sum = users.stream().mapToInt(u -> u.getAge()).sum();
        int total = users.stream().map(User::getAge).reduce(0, Integer::sum);
        Map<String, List<User>> byDept = users.stream().collect(Collectors.groupingBy(User::getDept));
        Map<String, Long> countByDept = users.stream()
                .collect(Collectors.groupingBy(User::getDept, Collectors.counting()));
        Map<Boolean, List<User>> part = users.stream().collect(Collectors.partitioningBy(User::isAdult));
        String joined = users.stream().map(User::getName).collect(Collectors.joining(", ", "[", "]"));
        Map<String, Integer> asMap = users.stream()
                .collect(Collectors.toMap(User::getName, User::getAge, (x, y) -> x));
        List<String> listOfListsJoin = users.stream()
                .flatMap(u -> Stream.of(u.getName(), u.getDept()))
                .collect(Collectors.toList());
        users.stream().peek(System.out::println).count();
        IntSummaryStatistics stats = users.stream().mapToInt(User::getAge).summaryStatistics();
        List<Integer> boxed = IntStream.range(0, 5).boxed().collect(Collectors.toList());
        users.parallelStream().count();

        Stream<String> once = users.stream().map(User::getName);
        once.count();   // reusing would throw IllegalStateException at runtime
    }

    // ---- section 15 ----
    static Optional<User> findUserById(int id) { return Optional.of(new User("x")); }
    static User createDefault() { return new User("def"); }
    static void welcome(User u) { }
    static class NotFoundException extends RuntimeException {
        NotFoundException(int id) { super("nf:" + id); }
    }

    public static void optionals() {
        Optional<User> u = findUserById(1);
        String name = u.map(User::getName).orElse("anonymous");
        u.ifPresent(x -> welcome(x));
        User or = u.orElseGet(() -> createDefault());
        User need = u.orElseThrow(() -> new NotFoundException(1));
        Optional<String> city = u.filter(x -> x.getAge() > 18).map(User::getName);
        boolean p = u.isPresent();
        String req = Objects.requireNonNull(name, "name");
        boolean safeEq = "literal".equals(name);
        boolean eq = Objects.equals(name, safeEq);
    }

    // ---- section 16 ----
    public static void strings(String s, String src, String input, List<String> parts) {
        int n = s.length();
        char c = s.charAt(0);
        String sub = s.substring(1, 4);
        boolean has = s.contains("xyz");
        String[] sp = s.split(",");
        String[] dotted = "a.b.c".split("\\.");
        String joined = String.join("-", sp);
        String trimmed = s.trim();
        String rep = s.replaceAll("\\d+", "#");
        String rep2 = s.replace("a", "b");
        String up = s.toUpperCase(Locale.ROOT);
        int idx = s.indexOf('@');
        String fmt = String.format("%s %%d %.2f%n", s, 1.0);

        StringBuilder sb = new StringBuilder();
        for (String p : parts) { sb.append(p).append(','); }
        String out = sb.deleteCharAt(sb.length() - 1).toString();

        boolean ok = input.matches("\\d{3}-\\d{4}");
        Matcher mm = Pattern.compile("(\\d+)-(\\d+)").matcher(src);
        while (mm.find()) { mm.group(1); mm.group(2); }
    }

    // ---- section 17 ----
    public static void time(LocalDateTime otherDt, LocalDate endDate) {
        LocalDate d = LocalDate.now();
        LocalDateTime dt = LocalDateTime.now();
        LocalTime t = LocalTime.of(9, 30);
        Instant ins = Instant.now();
        ZonedDateTime zdt = ZonedDateTime.of(dt, ZoneId.of("Asia/Shanghai"));

        LocalDate next = d.plusDays(1).withYear(2027);
        Duration between = Duration.between(dt, otherDt);
        Period p = Period.between(d, endDate);

        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
        String text = dt.format(fmt);
        LocalDateTime parsed = LocalDateTime.parse("2026-11-19 09:30:00", fmt);
        boolean cmp = d.isBefore(endDate) || d.isEqual(endDate) || d.compareTo(endDate) == 0;
    }

    // ---- section 18 ----
    static void process(String line) { }
    public static void io() throws IOException {
        Path base = Paths.get("data", "sub");
        List<String> lines = Files.readAllLines(Paths.get("a.txt"), StandardCharsets.UTF_8);
        byte[] raw = Files.readAllBytes(Paths.get("a.bin"));
        Files.write(Paths.get("out.txt"), "done\n".getBytes(StandardCharsets.UTF_8));
        Path p = Paths.get("a.txt");
        Files.exists(p); Files.isDirectory(p); Files.createDirectories(base);
        Files.copy(p, Paths.get("b.txt"), StandardCopyOption.REPLACE_EXISTING);
        try (Stream<String> big = Files.lines(Paths.get("huge.txt"))) {
            long n = big.filter(l -> !l.trim().isEmpty()).count();
        }
        File f = new File("in.txt");
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(new FileInputStream(f), StandardCharsets.UTF_8))) {
            String line;
            while ((line = br.readLine()) != null) { process(line); }
        }
        BigDecimal money = new BigDecimal("0.1");
        ObjectOutputStream oos = null;   // serialization mentioned as legacy only
    }

    // ---- section 19 ----
    static int heavyCompute() { return 42; }
    static class Job { }
    static String queryDb() { return "rows"; }
    static String transform(String rows) { return rows; }
    static String fallback() { return "fb"; }
    static void notify(String r) { }

    public static void concurrency() throws Exception {
        Runnable task = () -> System.out.println("running in " + Thread.currentThread().getName());
        Thread t = new Thread(task);
        t.start();
        t.join();

        ExecutorService pool = Executors.newFixedThreadPool(8);
        Future<Integer> fut = pool.submit(() -> heavyCompute());
        Integer r = fut.get(3, TimeUnit.SECONDS);
        pool.shutdown();

        ThreadPoolExecutor manual = new ThreadPoolExecutor(
                4, 8, 60L, TimeUnit.SECONDS, new ArrayBlockingQueue<Runnable>(100),
                new ThreadPoolExecutor.CallerRunsPolicy());
        manual.shutdown();

        Counter c = new Counter();
        c.inc();

        BlockingQueue<Job> queue = new ArrayBlockingQueue<>(100);
        queue.put(new Job());
        Job j = queue.poll(1, TimeUnit.SECONDS);

        CompletableFuture<Void> chain = CompletableFuture
                .supplyAsync(() -> queryDb(), pool)
                .thenApplyAsync(rows -> transform(rows), pool)
                .exceptionally(ex -> fallback())
                .thenAccept(result -> notify(result));   // returns CF<Void>, keep for join

        CompletableFuture<String> f1 = CompletableFuture.supplyAsync(GeneralGuideSnippets::queryDb, pool);
        CompletableFuture<String> f2 = CompletableFuture.supplyAsync(GeneralGuideSnippets::queryDb, pool);
        CompletableFuture<String> f3 = CompletableFuture.supplyAsync(GeneralGuideSnippets::queryDb, pool);
        CompletableFuture.allOf(f1, f2, f3).join();

        java.util.concurrent.atomic.AtomicInteger ai = new java.util.concurrent.atomic.AtomicInteger();
        ai.incrementAndGet();
        ConcurrentHashMap<String, Integer> chm = new ConcurrentHashMap<>();
        chm.computeIfAbsent("k", k -> 0);
        volatileFlag();
    }

    static class Counter {
        private int n;
        public synchronized void inc() { n++; }
    }

    static void volatileFlag() { }

    // ---- JUnit-style assertion usage is library-dependent; skip harness here (section 21 verified against JUnit 5.9 in java-practice project). ----

    public static void main(String[] args) { }
}
