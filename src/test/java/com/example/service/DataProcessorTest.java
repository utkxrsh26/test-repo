package com.example.service;

import com.example.service.DataProcessor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.function.Function;
import java.util.function.Predicate;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DataProcessor Tests")
class DataProcessorTest {

    private DataProcessor dataProcessor;

    @BeforeEach
    void setUp() {
        dataProcessor = new DataProcessor();
    }

    @AfterEach
    void tearDown() {
        dataProcessor.shutdown();
        dataProcessor = null;
    }

    @Test
    @DisplayName("Should create instance successfully")
    void testConstructor() {
        assertNotNull(dataProcessor);
    }

    // ---------------- processDataPipeline tests ----------------

    @Test
    @DisplayName("processDataPipeline should return empty map for null or empty input")
    void testProcessDataPipeline_NullOrEmptyInput() {
        Map<String, List<Integer>> resultNull =
                dataProcessor.<String, Integer>processDataPipeline(
                        null,
                        s -> true,
                        String::length,
                        Object::toString,
                        Comparator.naturalOrder()
                );
        assertNotNull(resultNull);
        assertTrue(resultNull.isEmpty());

        Map<String, List<Integer>> resultEmpty =
                dataProcessor.<String, Integer>processDataPipeline(
                        Collections.emptyList(),
                        s -> true,
                        String::length,
                        Object::toString,
                        Comparator.naturalOrder()
                );
        assertNotNull(resultEmpty);
        assertTrue(resultEmpty.isEmpty());
    }

    @Test
    @DisplayName("processDataPipeline should filter, transform, sort and group correctly")
    void testProcessDataPipeline_BasicBehavior() {
        List<String> data = Arrays.asList("apple", "banana", "apricot", "berry", "avocado");

        Predicate<String> filter = s -> s.startsWith("a");
        Function<String, Integer> transformer = String::length;
        Function<Integer, String> grouper = len -> len % 2 == 0 ? "even" : "odd";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<String, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertNotNull(result);
        assertEquals(2, result.size());
        assertTrue(result.containsKey("even"));
        assertTrue(result.containsKey("odd"));

        List<Integer> even = result.get("even");
        List<Integer> odd = result.get("odd");

        // apple(5), apricot(7), avocado(7)
        // lengths: 5,7,7 -> odd group: [5,7] after distinct and sort
        assertEquals(Arrays.asList(5, 7), odd);

        // even group should be empty
        assertTrue(even.isEmpty());
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls and apply distinct and limit per group")
    void testProcessDataPipeline_NullsDistinctAndLimit() {
        List<String> data = new ArrayList<>();
        for (int i = 0; i < 150; i++) {
            data.add("value" + (i % 3)); // only 3 distinct values
        }
        data.add(null);

        Predicate<String> filter = Objects::nonNull;
        Function<String, String> transformer = s -> s; // identity
        Function<String, String> grouper = s -> "group";
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result =
                dataProcessor.<String, String>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertNotNull(result);
        assertEquals(1, result.size());
        List<String> groupValues = result.get("group");
        // distinct of value0, value1, value2
        assertEquals(3, groupValues.size());
        assertTrue(groupValues.contains("value0"));
        assertTrue(groupValues.contains("value1"));
        assertTrue(groupValues.contains("value2"));
    }

    // ---------------- calculateStatistics & StatisticalResult tests ----------------

    @Test
    @DisplayName("calculateStatistics should throw for null or empty list")
    void testCalculateStatistics_NullOrEmpty() {
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(null));
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(Collections.emptyList()));
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for odd-sized list")
    void testCalculateStatistics_OddSizedList() {
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0, 4.0, 5.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(3.0, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(4.0, result.getQ3(), 0.0001);
        assertEquals(Math.sqrt(2.0), result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        double expectedMean = (10.0 + 20.0 + 30.0 + 40.0) / 4.0;
        double expectedMedian = (20.0 + 30.0) / 2.0;
        double expectedQ1 = 20.0; // 25th percentile in sorted [10,20,30,40]
        double expectedQ3 = 40.0; // 75th percentile

        assertEquals(expectedMean, result.getMean(), 0.0001);
        assertEquals(expectedMedian, result.getMedian(), 0.0001);
        assertEquals(expectedQ1, result.getQ1(), 0.0001);
        assertEquals(expectedQ3, result.getQ3(), 0.0001);
        assertTrue(result.getStandardDeviation() > 0.0);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should detect outliers using IQR method")
    void testCalculateStatistics_Outliers() {
        List<Double> values = Arrays.asList(10.0, 12.0, 11.0, 13.0, 12.5, 200.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(200.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("StatisticalResult getters should return immutable outliers list")
    void testStatisticalResult_Immutability() {
        List<Double> values = Arrays.asList(1.0, 2.0, 100.0);
        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertThrows(UnsupportedOperationException.class, () -> outliers.add(5.0));
    }

    // ---------------- processInParallel tests ----------------

    @Test
    @DisplayName("processInParallel should process all keys and return results map")
    void testProcessInParallel_Basic() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("a", "b", "c");

        Function<String, Integer> processor = String::length;

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        Map<String, Integer> result = future.get();

        assertNotNull(result);
        assertEquals(3, result.size());
        assertEquals(1, result.get("a"));
        assertEquals(1, result.get("b"));
        assertEquals(1, result.get("c"));
    }

    @Test
    @DisplayName("processInParallel should propagate processing exceptions as RuntimeException")
    void testProcessInParallel_ExceptionPropagation() {
        List<String> keys = Arrays.asList("ok", "fail", "alsoOk");

        Function<String, String> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("Failure");
            }
            return key.toUpperCase();
        };

        CompletableFuture<Map<String, String>> future =
                dataProcessor.<String>processInParallel(keys, processor);

        ExecutionException executionException =
                assertThrows(ExecutionException.class, future::get);

        assertTrue(executionException.getCause() instanceof RuntimeException);
        assertTrue(executionException.getCause().getMessage().contains("Processing failed for key: fail"));
    }

    @Test
    @DisplayName("processInParallel should keep first value on key collision")
    void testProcessInParallel_KeyCollision() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("k1", "k1", "k1");

        Function<String, String> processor = key -> UUID.randomUUID().toString();

        CompletableFuture<Map<String, String>> future =
                dataProcessor.<String>processInParallel(keys, processor);

        Map<String, String> result = future.get();

        assertNotNull(result);
        assertEquals(1, result.size());
        assertTrue(result.containsKey("k1"));
        assertNotNull(result.get("k1"));
    }

    // ---------------- findShortestPaths tests ----------------

    @Test
    @DisplayName("findShortestPaths should throw for null graph or invalid start node")
    void testFindShortestPaths_InvalidInput() {
        assertThrows(IllegalArgumentException.class,
                () -> dataProcessor.findShortestPaths(null, "A"));

        Map<String, Map<String, Integer>> graph = new HashMap<>();
        graph.put("A", Collections.singletonMap("B", 1));

        assertThrows(IllegalArgumentException.class,
                () -> dataProcessor.findShortestPaths(graph, "Z"));
    }

    @Test
    @DisplayName("findShortestPaths should compute correct shortest paths in simple graph")
    void testFindShortestPaths_SimpleGraph() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();

        Map<String, Integer> neighborsA = new HashMap<>();
        neighborsA.put("B", 1);
        neighborsA.put("C", 4);

        Map<String, Integer> neighborsB = new HashMap<>();
        neighborsB.put("C", 2);
        neighborsB.put("D", 5);

        Map<String, Integer> neighborsC = new HashMap<>();
        neighborsC.put("D", 1);

        graph.put("A", neighborsA);
        graph.put("B", neighborsB);
        graph.put("C", neighborsC);
        graph.put("D", new HashMap<>());

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(1, distances.get("B").intValue());
        assertEquals(3, distances.get("C").intValue()); // A->B->C
        assertEquals(4, distances.get("D").intValue()); // A->B->C->D
    }

    @Test
    @DisplayName("findShortestPaths should handle disconnected nodes")
    void testFindShortestPaths_DisconnectedGraph() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();

        graph.put("A", Collections.singletonMap("B", 2));
        graph.put("B", new HashMap<>());
        graph.put("C", new HashMap<>()); // disconnected

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(2, distances.get("B").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("C").intValue());
    }
}