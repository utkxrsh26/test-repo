package com.example.service;

import com.example.service.DataProcessor;
import com.example.service.DataProcessor.StatisticalResult;
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
        Function<String, String> transformer = String::toUpperCase;
        Function<String, String> grouper = s -> s.substring(0, 1); // group by first letter
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result =
                dataProcessor.<String, String>processDataPipeline(
                        data, filter, transformer, grouper, sorter);

        assertEquals(1, result.size());
        assertTrue(result.containsKey("A"));

        List<String> groupA = result.get("A");
        assertNotNull(groupA);
        // original "apple", "apricot", "avocado" -> transformed and sorted
        assertEquals(3, groupA.size());
        assertEquals(Arrays.asList("APPLE", "APRICOT", "AVOCADO"), groupA);
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls after transformation")
    void testProcessDataPipeline_NullAfterTransform() {
        List<String> data = Arrays.asList("a", "b", "c");

        Predicate<String> filter = s -> true;
        Function<String, String> transformer = s -> "b".equals(s) ? null : s;
        Function<String, String> grouper = s -> "group";
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result =
                dataProcessor.<String, String>processDataPipeline(
                        data, filter, transformer, grouper, sorter);

        assertEquals(1, result.size());
        List<String> group = result.get("group");
        assertNotNull(group);
        assertEquals(2, group.size());
        assertTrue(group.contains("a"));
        assertTrue(group.contains("c"));
    }

    @Test
    @DisplayName("processDataPipeline should deduplicate and limit to 100 per group")
    void testProcessDataPipeline_DeduplicationAndLimit() {
        List<Integer> data = new ArrayList<>();
        // create 150 identical values so after distinct and limit we get 1
        for (int i = 0; i < 150; i++) {
            data.add(1);
        }

        Predicate<Integer> filter = i -> true;
        Function<Integer, Integer> transformer = i -> i;
        Function<Integer, String> grouper = i -> "all";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter);

        assertEquals(1, result.size());
        List<Integer> group = result.get("all");
        assertNotNull(group);
        // distinct should reduce to a single element
        assertEquals(1, group.size());
        assertEquals(1, group.get(0));
    }

    @Test
    @DisplayName("processDataPipeline should enforce limit of 100 per group with many distinct values")
    void testProcessDataPipeline_Limit100PerGroup() {
        List<Integer> data = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            data.add(i);
        }

        Predicate<Integer> filter = i -> true;
        Function<Integer, Integer> transformer = i -> i;
        Function<Integer, String> grouper = i -> "all";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter);

        List<Integer> group = result.get("all");
        assertNotNull(group);
        assertEquals(100, group.size());
        // should contain the first 100 distinct sorted values
        assertEquals(0, group.get(0));
        assertEquals(99, group.get(99));
    }

    // ----------------------------------------------------------------------
    // calculateStatistics / StatisticalResult tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("calculateStatistics should throw for null or empty list")
    void testCalculateStatistics_NullOrEmpty() {
        assertThrows(IllegalArgumentException.class,
                () -> dataProcessor.calculateStatistics(null));

        assertThrows(IllegalArgumentException.class,
                () -> dataProcessor.calculateStatistics(Collections.emptyList()));
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for odd-sized list")
    void testCalculateStatistics_OddSizedList() {
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0, 4.0, 5.0);

        StatisticalResult result = dataProcessor.calculateStatistics(values);

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

        StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(25.0, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);
        // sorted: 10,20,30,40
        // q1 at 25th percentile -> between 10 and 20 -> 10 (per implementation using index)
        // q3 at 75th percentile -> between 30 and 40 -> 30
        assertEquals(10.0, result.getQ1(), 0.0001);
        assertEquals(30.0, result.getQ3(), 0.0001);
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
        // Mostly clustered around 10-20, with one large outlier 100
        List<Double> values = Arrays.asList(10.0, 12.0, 13.0, 15.0, 18.0, 20.0, 100.0);

        StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(100.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("StatisticalResult getters should return immutable outliers list")
    void testStatisticalResult_Immutability() {
        List<Double> values = Arrays.asList(1.0, 2.0, 100.0);
        StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertThrows(UnsupportedOperationException.class, () -> outliers.add(200.0));
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

        assertEquals(3, result.size());
        assertEquals(1, result.get("a"));
        assertEquals(1, result.get("b"));
        assertEquals(1, result.get("c"));
    }

    @Test
    @DisplayName("processInParallel should propagate exceptions as RuntimeException")
    void testProcessInParallel_ExceptionPropagation() {
        List<String> keys = Arrays.asList("ok", "fail");

        Function<String, Integer> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("boom");
            }
            return key.length();
        };

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        ExecutionException executionException =
                assertThrows(ExecutionException.class, future::get);

        assertTrue(executionException.getCause() instanceof RuntimeException);
        assertTrue(executionException.getCause().getMessage().contains("Processing failed for key: fail"));
    }

    @Test
    @DisplayName("processInParallel should keep first value on key collision")
    void testProcessInParallel_KeyCollisionKeepsFirst() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("x", "x", "x");

        Function<String, Integer> processor = key -> key.length() + new Random().nextInt(100);

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        Map<String, Integer> result = future.get();

        assertEquals(1, result.size());
        assertTrue(result.containsKey("x"));
    }

    // ----------------------------------------------------------------------
    // findShortestPaths tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("findShortestPaths should throw for null graph or missing start node")
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

        assertEquals(0, distances.get("A").intValue());
        assertEquals(1, distances.get("B").intValue());
        assertEquals(3, distances.get("C").intValue()); // A->B->C
        assertEquals(4, distances.get("D").intValue()); // A->B->C->D
    }

    @Test
    @DisplayName("findShortestPaths should handle disconnected nodes")
    void testFindShortestPaths_DisconnectedNodes() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();
        graph.put("A", Collections.singletonMap("B", 2));
        graph.put("B", new HashMap<>());
        graph.put("C", new HashMap<>()); // disconnected

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(2, distances.get("B").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("C").intValue());
    }

    // ----------------------------------------------------------------------
    // shutdown tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("shutdown should be callable multiple times without error")
    void testShutdown_Idempotent() {
        dataProcessor.shutdown();
        // calling again should not throw
        dataProcessor.shutdown();
    }
}