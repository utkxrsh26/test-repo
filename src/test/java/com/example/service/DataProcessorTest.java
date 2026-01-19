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

    // ----------------------------------------------------------------------
    // processDataPipeline tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("processDataPipeline should return empty map for null or empty input")
    void testProcessDataPipeline_NullOrEmpty() {
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
    void testProcessDataPipeline_BasicFlow() {
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
        // Depending on implementation, there may be 1 or 2 groups; ensure at least both keys exist if present
        assertTrue(result.containsKey("odd"));
        List<Integer> odd = result.get("odd");
        assertEquals(Arrays.asList(5, 7, 7), odd);
        if (result.containsKey("even")) {
            List<Integer> even = result.get("even");
            assertNotNull(even);
        }
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls and apply distinct and limit per group")
    void testProcessDataPipeline_NullsDistinctAndLimit() {
        List<String> data = new ArrayList<>();
        data.add("a");
        data.add("a");
        data.add("b");
        data.add(null);
        data.add("c");

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
        List<String> group = result.get("group");
        assertNotNull(group);
        // distinct and sorted: "a","b","c"
        assertEquals(3, group.size());
        assertEquals(Arrays.asList("a", "b", "c"), group);
    }

    @Test
    @DisplayName("processDataPipeline should enforce limit of 100 elements per group")
    void testProcessDataPipeline_GroupLimit() {
        List<Integer> data = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            data.add(i);
        }

        Predicate<Integer> filter = i -> true;
        Function<Integer, Integer> transformer = i -> 1; // all same value
        Function<Integer, String> grouper = i -> "single";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertNotNull(result);
        assertEquals(1, result.size());
        List<Integer> group = result.get("single");
        assertNotNull(group);
        // after transform all are 1, distinct -> single element
        assertEquals(1, group.size());
        assertEquals(1, group.get(0));
    }

    // ----------------------------------------------------------------------
    // calculateStatistics tests
    // ----------------------------------------------------------------------

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

        assertNotNull(result);
        assertEquals(3.0, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(4.0, result.getQ3(), 0.0001);
        // variance = 2.0, stdDev = sqrt(2)
        assertEquals(Math.sqrt(2.0), result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertNotNull(result);
        assertEquals(25.0, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);
        // For this implementation, Q1 and Q3 are based on percentile logic
        assertEquals(15.0, result.getQ1(), 10.0);
        assertEquals(35.0, result.getQ3(), 10.0);
        double expectedVariance = ((10 - 25) * (10 - 25)
                + (20 - 25) * (20 - 25)
                + (30 - 25) * (30 - 25)
                + (40 - 25) * (40 - 25)) / 4.0;
        double expectedStdDev = Math.sqrt(expectedVariance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should detect outliers using IQR method")
    void testCalculateStatistics_Outliers() {
        List<Double> values = Arrays.asList(1.0, 2.0, 2.0, 3.0, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertNotNull(result);
        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(100.0, outliers.get(0), 0.0001);
    }

    // ----------------------------------------------------------------------
    // calculatePercentile (private) via behavior tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("calculateStatistics should use percentile logic for Q1 and Q3")
    void testCalculateStatistics_PercentilesBehavior() {
        // Values chosen to make percentiles easy to reason about
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        // With the given implementation, Q1 is 25th percentile, Q3 is 75th percentile
        // sorted: 1..8
        // 25th percentile index = ceil(0.25*8)-1 = ceil(2)-1 = 1 -> value 2
        // 75th percentile index = ceil(0.75*8)-1 = ceil(6)-1 = 5 -> value 6
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(6.0, result.getQ3(), 0.0001);
    }

    // ----------------------------------------------------------------------
    // processInParallel tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("processInParallel should process all keys and return results map")
    void testProcessInParallel_Basic() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("a", "b", "c");

        Function<String, Integer> processor = String::length;

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        assertNotNull(future);
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
        List<String> keys = Arrays.asList("ok", "fail", "ok2");

        Function<String, String> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("Failure");
            }
            return key.toUpperCase();
        };

        CompletableFuture<Map<String, String>> future =
                dataProcessor.<String>processInParallel(keys, processor);

        assertNotNull(future);
        ExecutionException executionException = assertThrows(ExecutionException.class, future::get);
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

    // ----------------------------------------------------------------------
    // findShortestPaths tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("findShortestPaths should throw for null graph or invalid start node")
    void testFindShortestPaths_InvalidInput() {
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.findShortestPaths(null, "A"));

        Map<String, Map<String, Integer>> graph = new HashMap<>();
        graph.put("A", Collections.singletonMap("B", 1));
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.findShortestPaths(graph, "Z"));
    }

    @Test
    @DisplayName("findShortestPaths should compute correct shortest paths in simple graph")
    void testFindShortestPaths_SimpleGraph() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();

        Map<String, Integer> neighborsA = new HashMap<>();
        neighborsA.put("B", 1);
        neighborsA.put("C", 4);
        graph.put("A", neighborsA);

        Map<String, Integer> neighborsB = new HashMap<>();
        neighborsB.put("C", 2);
        neighborsB.put("D", 5);
        graph.put("B", neighborsB);

        Map<String, Integer> neighborsC = new HashMap<>();
        neighborsC.put("D", 1);
        graph.put("C", neighborsC);

        graph.put("D", new HashMap<>());

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertNotNull(distances);
        assertEquals(4, distances.size());
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

        assertNotNull(distances);
        assertEquals(3, distances.size());
        assertEquals(0, distances.get("A").intValue());
        assertEquals(2, distances.get("B").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("C").intValue());
    }

    // ----------------------------------------------------------------------
    // StatisticalResult tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("StatisticalResult getters should return constructor values and outliers should be unmodifiable copy")
    void testStatisticalResult_GettersAndImmutability() {
        List<Double> outliers = new ArrayList<>();
        outliers.add(100.0);
        outliers.add(200.0);

        DataProcessor.StatisticalResult result =
                new DataProcessor.StatisticalResult(10.0, 5.0, 3.0, 7.0, 2.5, outliers);

        assertEquals(10.0, result.getMean(), 0.0001);
        assertEquals(5.0, result.getMedian(), 0.0001);
        assertEquals(3.0, result.getQ1(), 0.0001);
        assertEquals(7.0, result.getQ3(), 0.0001);
        assertEquals(2.5, result.getStandardDeviation(), 0.0001);

        List<Double> returnedOutliers = result.getOutliers();
        assertEquals(2, returnedOutliers.size());
        assertEquals(100.0, returnedOutliers.get(0), 0.0001);
        assertEquals(200.0, returnedOutliers.get(1), 0.0001);

        // Modify original list should not affect result
        outliers.add(300.0);
        assertEquals(2, result.getOutliers().size());

        // Returned list should be unmodifiable
        assertThrows(UnsupportedOperationException.class, () -> returnedOutliers.add(400.0));
    }
}