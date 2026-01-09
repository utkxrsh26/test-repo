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
        Map<String, List<Integer>> resultNull =
                dataProcessor.<String, Integer>processDataPipeline(
                        null,
                        s -> true,
                        String::length,
                        len -> "group",
                        Comparator.naturalOrder()
                );
        assertNotNull(resultNull);
        assertTrue(resultNull.isEmpty());

        Map<String, List<Integer>> resultEmpty =
                dataProcessor.<String, Integer>processDataPipeline(
                        Collections.emptyList(),
                        s -> true,
                        String::length,
                        len -> "group",
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
        assertEquals(2, result.size());
        assertTrue(result.containsKey("even"));
        assertTrue(result.containsKey("odd"));

        List<Integer> even = result.get("even");
        List<Integer> odd = result.get("odd");

        // "apple"(5), "apricot"(7), "avocado"(7)
        // lengths: 5,7,7 -> odd group: [5,7] after distinct and sort
        assertEquals(Arrays.asList(5, 7), odd);

        // even group should be empty
        assertTrue(even.isEmpty());
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls after transformation")
    void testProcessDataPipeline_RemoveNulls() {
        List<String> data = Arrays.asList("a", "bb", "ccc", "dddd");

        Function<String, Integer> transformer = s -> {
            if (s.length() == 2) {
                return null;
            }
            return s.length();
        };

        Map<String, List<Integer>> result =
                dataProcessor.<String, Integer>processDataPipeline(
                        data,
                        s -> true,
                        transformer,
                        len -> "all",
                        Comparator.naturalOrder()
                );

        assertNotNull(result);
        assertEquals(1, result.size());
        List<Integer> all = result.get("all");
        assertEquals(Arrays.asList(1, 3, 4), all);
    }

    @Test
    @DisplayName("processDataPipeline should deduplicate and limit to 100 per group")
    void testProcessDataPipeline_DedupAndLimit() {
        List<Integer> data = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            data.add(i % 10); // many duplicates of 0..9
        }

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data,
                        v -> true,
                        v -> v,
                        v -> "group",
                        Comparator.naturalOrder()
                );

        assertNotNull(result);
        assertEquals(1, result.size());
        List<Integer> group = result.get("group");

        // distinct of 0..9 -> 10 elements, limit 100 should not cut them
        assertEquals(10, group.size());
        assertEquals(Arrays.asList(0, 1, 2, 3, 4, 5, 6, 7, 8, 9), group);
    }

    // -------------------------------------------------------------------------
    // calculateStatistics tests
    // -------------------------------------------------------------------------

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

        // variance = 2.0, stdDev = sqrt(2)
        assertEquals(Math.sqrt(2.0), result.getStandardDeviation(), 0.0001);
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        // mean = 25
        assertEquals(25.0, result.getMean(), 0.0001);
        // median = (20 + 30) / 2 = 25
        assertEquals(25.0, result.getMedian(), 0.0001);

        // sorted: 10,20,30,40
        // percentile 25: index = ceil(0.25*4)-1 = ceil(1)-1 = 0 -> 10
        // percentile 75: index = ceil(0.75*4)-1 = ceil(3)-1 = 2 -> 30
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
        // Mostly 10..14, with one big outlier 100
        List<Double> values = Arrays.asList(10.0, 11.0, 12.0, 13.0, 14.0, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(100.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("calculateStatistics should return unmodifiable outliers list")
    void testCalculateStatistics_OutliersUnmodifiable() {
        List<Double> values = Arrays.asList(1.0, 2.0, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);
        List<Double> outliers = result.getOutliers();

        assertThrows(UnsupportedOperationException.class, () -> outliers.add(200.0));
    }

    @Test
    @DisplayName("calculateStatistics should handle single-element list")
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

    // -------------------------------------------------------------------------
    // processInParallel tests
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("processInParallel should process all keys and return results map")
    void testProcessInParallel_Basic() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("a", "bb", "ccc");

        Function<String, Integer> processor = String::length;

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        assertNotNull(future);
        Map<String, Integer> result = future.get();

        assertEquals(3, result.size());
        assertEquals(1, result.get("a"));
        assertEquals(2, result.get("bb"));
        assertEquals(3, result.get("ccc"));
    }

    @Test
    @DisplayName("processInParallel should propagate exceptions from processor")
    void testProcessInParallel_ProcessorException() {
        List<String> keys = Arrays.asList("ok", "fail", "alsoOk");

        Function<String, Integer> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("Failure for key: " + key);
            }
            return key.length();
        };

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        ExecutionException executionException = assertThrows(ExecutionException.class, future::get);
        assertTrue(executionException.getCause() instanceof RuntimeException);
        assertTrue(executionException.getCause().getMessage().contains("Processing failed for key: fail"));
    }

    @Test
    @DisplayName("processInParallel should keep first value on key collision")
    void testProcessInParallel_KeyCollision() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("same", "same", "same");

        Function<String, Integer> processor = key -> key.length();

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        Map<String, Integer> result = future.get();

        assertEquals(1, result.size());
        assertTrue(result.containsKey("same"));
        assertEquals("same".length(), result.get("same"));
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
    @DisplayName("findShortestPaths should compute shortest paths in simple graph")
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

        Map<String, Integer> neighborsD = new HashMap<>();

        graph.put("A", neighborsA);
        graph.put("B", neighborsB);
        graph.put("C", neighborsC);
        graph.put("D", neighborsD);

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
        graph.put("B", Collections.emptyMap());
        graph.put("C", Collections.emptyMap()); // disconnected

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(2, distances.get("B").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("C").intValue());
    }

    @Test
    @DisplayName("findShortestPaths should handle graph with no outgoing edges from start")
    void testFindShortestPaths_NoOutgoingEdges() {
        Map<String, Map<String, Integer>> graph = new HashMap<>();
        graph.put("A", Collections.emptyMap());
        graph.put("B", Collections.emptyMap());

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertEquals(0, distances.get("A").intValue());
        assertEquals(Integer.MAX_VALUE, distances.get("B").intValue());
    }
}