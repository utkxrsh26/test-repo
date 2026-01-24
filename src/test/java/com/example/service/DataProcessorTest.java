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
    @DisplayName("processDataPipeline should return empty map for null or empty input")
    void testProcessDataPipeline_NullOrEmpty() {
        Map<String, List<Integer>> resultNull = dataProcessor.<String, Integer>processDataPipeline(
                null,
                s -> true,
                String::length,
                Object::toString,
                Comparator.naturalOrder()
        );
        assertNotNull(resultNull);
        assertTrue(resultNull.isEmpty());

        Map<String, List<Integer>> resultEmpty = dataProcessor.<String, Integer>processDataPipeline(
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

        Map<String, List<Integer>> result = dataProcessor.<String, Integer>processDataPipeline(
                data, filter, transformer, grouper, sorter
        );

        assertNotNull(result);
        assertTrue(result.containsKey("odd"));
        assertFalse(result.containsKey("even"));

        List<Integer> oddGroup = result.get("odd");
        assertEquals(Arrays.asList(5, 7), oddGroup);
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls and apply distinct and limit per group")
    void testProcessDataPipeline_NullsDistinctAndLimit() {
        List<String> data = new ArrayList<>();
        for (int i = 0; i < 150; i++) {
            data.add("x"); // same value to test distinct
        }
        data.add(null);

        Predicate<String> filter = Objects::nonNull;
        Function<String, String> transformer = s -> s; // identity
        Function<String, String> grouper = s -> "group";
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result = dataProcessor.<String, String>processDataPipeline(
                data, filter, transformer, grouper, sorter
        );

        assertNotNull(result);
        assertTrue(result.containsKey("group"));
        List<String> group = result.get("group");

        // distinct should reduce to single "x"
        assertEquals(1, group.size());
        assertEquals("x", group.get(0));
    }

    @Test
    @DisplayName("processDataPipeline should respect custom sorter")
    void testProcessDataPipeline_Sorter() {
        List<Integer> data = Arrays.asList(5, 1, 3, 2, 4);

        Predicate<Integer> filter = i -> i > 1;
        Function<Integer, Integer> transformer = i -> i;
        Function<Integer, String> grouper = i -> "all";
        Comparator<Integer> sorter = Comparator.reverseOrder();

        Map<String, List<Integer>> result = dataProcessor.<Integer, Integer>processDataPipeline(
                data, filter, transformer, grouper, sorter
        );

        List<Integer> list = result.get("all");
        assertEquals(Arrays.asList(5, 4, 3, 2), list);
    }

    // -------------------------------------------------------------------------
    // calculateStatistics / StatisticalResult tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("calculateStatistics should throw for null or empty list")
    void testCalculateStatistics_NullOrEmpty() {
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(null));
        assertThrows(IllegalArgumentException.class, () -> dataProcessor.calculateStatistics(Collections.emptyList()));
    }

    @Test
    @DisplayName("calculateStatistics should compute correct mean, median, quartiles and std dev for odd-sized list")
    void testCalculateStatistics_OddSizedList() {
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0, 4.0, 5.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(3.0, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(4.0, result.getQ3(), 0.0001);
        assertEquals(1.4142, result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct values for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(25.0, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);
        assertEquals(20.0, result.getQ1(), 0.0001);
        assertEquals(35.0, result.getQ3(), 0.0001);
        assertEquals(12.9099, result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should detect outliers using IQR method")
    void testCalculateStatistics_Outliers() {
        List<Double> values = Arrays.asList(10.0, 12.0, 11.0, 13.0, 12.5, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(100.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("StatisticalResult should be immutable for outliers list")
    void testStatisticalResult_Immutability() {
        List<Double> values = Arrays.asList(1.0, 2.0, 3.0);
        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertThrows(UnsupportedOperationException.class, () -> outliers.add(10.0));
    }

    // -------------------------------------------------------------------------
    // processInParallel tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("processInParallel should process all keys and return a completed future")
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
    @DisplayName("processInParallel should propagate processing exceptions as RuntimeException")
    void testProcessInParallel_ExceptionPropagation() {
        List<String> keys = Arrays.asList("ok", "fail");

        Function<String, String> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("Failure");
            }
            return key.toUpperCase();
        };

        CompletableFuture<Map<String, String>> future =
                dataProcessor.<String>processInParallel(keys, processor);

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

        assertEquals(1, result.size());
        assertTrue(result.containsKey("k1"));
        assertNotNull(result.get("k1"));
    }

    // -------------------------------------------------------------------------
    // findShortestPaths tests
    // -------------------------------------------------------------------------

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

        assertEquals(0, distances.get("A").intValue());
        assertEquals(1, distances.get("B").intValue());
        assertEquals(3, distances.get("C").intValue());
        assertEquals(4, distances.get("D").intValue());
    }

    @Test
    @DisplayName("findShortestPaths should handle disconnected nodes")
    void testFindShortestPaths_DisconnectedNodes() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();

        graph.put("A", Collections.singletonMap("B", 2));
        graph.put("B", new HashMap<>());
        graph.put("C", new HashMap<>());

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(2, distances.get("B").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("C").intValue());
    }
}