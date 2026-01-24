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

    // -------------------------------------------------------------------------
    // processDataPipeline tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("processDataPipeline - should return empty map for null or empty input")
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
    @DisplayName("processDataPipeline - should filter, transform, sort and group correctly")
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
        assertTrue(result.containsKey("odd"));
        assertFalse(result.containsKey("even"));

        List<Integer> oddGroup = result.get("odd");
        assertNotNull(oddGroup);
        // "apple"(5), "apricot"(7), "avocado"(7) -> distinct and sorted: [5,7]
        assertEquals(2, oddGroup.size());
        assertEquals(Arrays.asList(5, 7), oddGroup);
    }

    @Test
    @DisplayName("processDataPipeline - should remove nulls after transformation")
    void testProcessDataPipeline_NullAfterTransform() {
        List<String> data = Arrays.asList("keep", "drop");

        Function<String, String> transformer = s -> "drop".equals(s) ? null : s.toUpperCase();
        Predicate<String> filter = s -> true;
        Function<String, String> grouper = s -> "group";
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result =
                dataProcessor.<String, String>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertEquals(1, result.size());
        List<String> group = result.get("group");
        assertNotNull(group);
        assertEquals(1, group.size());
        assertEquals("KEEP", group.get(0));
    }

    @Test
    @DisplayName("processDataPipeline - should deduplicate and limit to 100 per group")
    void testProcessDataPipeline_DeduplicationAndLimit() {
        List<Integer> data = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            data.add(i % 10); // many duplicates of 0..9
        }

        Predicate<Integer> filter = i -> true;
        Function<Integer, Integer> transformer = i -> i;
        Function<Integer, String> grouper = i -> "all";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertEquals(1, result.size());
        List<Integer> group = result.get("all");
        assertNotNull(group);
        // distinct of 0..9 -> 10 elements, less than limit 100
        assertEquals(10, group.size());
        assertEquals(Arrays.asList(0,1,2,3,4,5,6,7,8,9), group);
    }

    // -------------------------------------------------------------------------
    // calculateStatistics / StatisticalResult tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("calculateStatistics - should throw for null or empty list")
    void testCalculateStatistics_NullOrEmpty() {
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(null));
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(Collections.emptyList()));
    }

    @Test
    @DisplayName("calculateStatistics - should compute correct statistics for odd-sized list")
    void testCalculateStatistics_OddSizedList() {
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0, 4.0, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        double expectedMean = (1.0 + 2.0 + 3.0 + 4.0 + 100.0) / 5.0;
        assertEquals(expectedMean, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);

        // Sorted: [1,2,3,4,100]
        // Q1: ceil(0.25*5)=2 -> index1 -> 2
        // Q3: ceil(0.75*5)=4 -> index3 -> 4
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(4.0, result.getQ3(), 0.0001);

        // Standard deviation
        double mean = expectedMean;
        double variance = (Math.pow(1 - mean, 2) +
                Math.pow(2 - mean, 2) +
                Math.pow(3 - mean, 2) +
                Math.pow(4 - mean, 2) +
                Math.pow(100 - mean, 2)) / 5.0;
        double expectedStdDev = Math.sqrt(variance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        // IQR = 2, bounds: -1, 7 -> 100 is outlier
        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(100.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("calculateStatistics - should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        double expectedMean = (10.0 + 20.0 + 30.0 + 40.0) / 4.0;
        assertEquals(expectedMean, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);

        // Sorted: [10,20,30,40]
        // Q1: ceil(0.25*4)=1 -> index0 -> 10
        // Q3: ceil(0.75*4)=3 -> index2 -> 30
        assertEquals(10.0, result.getQ1(), 0.0001);
        assertEquals(30.0, result.getQ3(), 0.0001);

        double mean = expectedMean;
        double variance = (Math.pow(10 - mean, 2) +
                Math.pow(20 - mean, 2) +
                Math.pow(30 - mean, 2) +
                Math.pow(40 - mean, 2)) / 4.0;
        double expectedStdDev = Math.sqrt(variance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics - should handle single-element list")
    void testCalculateStatistics_SingleElement() {
        List<Double> values = Collections.singletonList(42.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(42.0, result.getMean(), 0.0001);
        assertEquals(42.0, result.getMedian(), 0.0001);
        assertEquals(42.0, result.getQ1(), 0.0001);
        assertEquals(42.0, result.getQ3(), 0.0001);
        assertEquals(0.0, result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("StatisticalResult - getters should return immutable outliers list")
    void testStatisticalResult_Immutability() {
        List<Double> values = Arrays.asList(1.0, 2.0, 100.0);
        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertThrows(UnsupportedOperationException.class, () -> outliers.add(5.0));
    }

    // -------------------------------------------------------------------------
    // processInParallel tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("processInParallel - should process keys in parallel and return results")
    void testProcessInParallel_Basic() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("a", "b", "c");

        Function<String, Integer> processor = s -> s.charAt(0) - 'a';

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        Map<String, Integer> result = future.get();

        assertEquals(3, result.size());
        assertEquals(0, result.get("a"));
        assertEquals(1, result.get("b"));
        assertEquals(2, result.get("c"));
    }

    @Test
    @DisplayName("processInParallel - should wrap exceptions in RuntimeException")
    void testProcessInParallel_ExceptionWrapping() {
        List<String> keys = Arrays.asList("ok", "fail");

        Function<String, String> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("boom");
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
    @DisplayName("processInParallel - should keep first value on key collision")
    void testProcessInParallel_KeyCollision() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("x", "x", "x");

        Function<String, Integer> processor = s -> new Random().nextInt(1000);

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        Map<String, Integer> result = future.get();

        assertEquals(1, result.size());
        assertTrue(result.containsKey("x"));
    }

    // -------------------------------------------------------------------------
    // findShortestPaths tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("findShortestPaths - should throw for null graph or invalid start node")
    void testFindShortestPaths_InvalidInput() {
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.findShortestPaths(null, "A"));

        Map<String, Map<String, Integer>> graph = new HashMap<>();
        graph.put("A", Collections.singletonMap("B", 1));
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.findShortestPaths(graph, "Z"));
    }

    @Test
    @DisplayName("findShortestPaths - should compute shortest paths in simple graph")
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
    @DisplayName("findShortestPaths - should handle disconnected nodes")
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