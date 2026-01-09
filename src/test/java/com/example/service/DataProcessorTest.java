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
    @DisplayName("processDataPipeline should filter, transform, sort, group and deduplicate correctly")
    void testProcessDataPipeline_NormalFlow() {
        List<String> data = Arrays.asList("apple", "banana", "apricot", "avocado", "banana", "apple");

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
        // apple(5), apricot(7), avocado(7), apple(5) -> after distinct and sort: [5,7]
        assertEquals(2, oddGroup.size());
        assertEquals(Arrays.asList(5, 7), oddGroup);
    }

    @Test
    @DisplayName("processDataPipeline should limit results per group to 100 and deduplicate")
    void testProcessDataPipeline_LimitAndDistinct() {
        List<Integer> data = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            data.add(i % 10); // many duplicates of 0-9
        }

        Predicate<Integer> filter = i -> true;
        Function<Integer, Integer> transformer = i -> i;
        Function<Integer, String> grouper = i -> "all";
        Comparator<Integer> sorter = Comparator.naturalOrder();

        Map<String, List<Integer>> result =
                dataProcessor.<Integer, Integer>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertNotNull(result);
        assertTrue(result.containsKey("all"));
        List<Integer> list = result.get("all");
        // distinct of 0-9 -> 10 elements, limit 100 should not cut them
        assertEquals(10, list.size());
        assertEquals(Arrays.asList(0,1,2,3,4,5,6,7,8,9), list);
    }

    @Test
    @DisplayName("processDataPipeline should ignore nulls after transformation")
    void testProcessDataPipeline_NullAfterTransform() {
        List<String> data = Arrays.asList("a", "b", "c");

        Predicate<String> filter = s -> true;
        Function<String, String> transformer = s -> "b".equals(s) ? null : s.toUpperCase();
        Function<String, String> grouper = s -> "group";
        Comparator<String> sorter = Comparator.naturalOrder();

        Map<String, List<String>> result =
                dataProcessor.<String, String>processDataPipeline(
                        data, filter, transformer, grouper, sorter
                );

        assertNotNull(result);
        List<String> list = result.get("group");
        assertNotNull(list);
        assertEquals(2, list.size());
        assertEquals(Arrays.asList("A", "C"), list);
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

        StatisticalResult result = dataProcessor.calculateStatistics(values);
        assertNotNull(result);

        assertEquals(3.0, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);
        assertEquals(1.5, result.getQ1(), 0.0001);
        assertEquals(4.5, result.getQ3(), 0.0001);

        double expectedVariance = (4 + 1 + 0 + 1 + 4) / 5.0;
        double expectedStdDev = Math.sqrt(expectedVariance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        StatisticalResult result = dataProcessor.calculateStatistics(values);
        assertNotNull(result);

        assertEquals(25.0, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);
        assertEquals(15.0, result.getQ1(), 0.0001);
        assertEquals(35.0, result.getQ3(), 0.0001);

        double expectedVariance = (225 + 25 + 25 + 225) / 4.0;
        double expectedStdDev = Math.sqrt(expectedVariance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should detect outliers using IQR method")
    void testCalculateStatistics_Outliers() {
        List<Double> values = Arrays.asList(10.0, 12.0, 13.0, 12.5, 11.5, 200.0);

        StatisticalResult result = dataProcessor.calculateStatistics(values);
        assertNotNull(result);

        List<Double> outliers = result.getOutliers();
        assertEquals(1, outliers.size());
        assertEquals(200.0, outliers.get(0), 0.0001);
    }

    @Test
    @DisplayName("StatisticalResult should be immutable and expose unmodifiable outliers list")
    void testStatisticalResult_Immutability() {
        List<Double> values = Arrays.asList(1.0, 2.0, 100.0);
        StatisticalResult result = dataProcessor.calculateStatistics(values);

        List<Double> outliers = result.getOutliers();
        assertThrows(UnsupportedOperationException.class, () -> outliers.add(5.0));
    }

    // ----------------------------------------------------------------------
    // processInParallel tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("processInParallel should process all keys and return a completed future")
    void testProcessInParallel_NormalFlow() throws ExecutionException, InterruptedException {
        List<String> keys = Arrays.asList("a", "b", "c");

        Function<String, String> processor = k -> k.toUpperCase();

        CompletableFuture<Map<String, String>> future =
                dataProcessor.<String>processInParallel(keys, processor);

        assertNotNull(future);
        Map<String, String> result = future.get();
        assertNotNull(result);
        assertEquals(3, result.size());
        assertEquals("A", result.get("a"));
        assertEquals("B", result.get("b"));
        assertEquals("C", result.get("c"));
    }

    @Test
    @DisplayName("processInParallel should propagate exceptions from processor")
    void testProcessInParallel_ProcessorThrows() {
        List<String> keys = Arrays.asList("ok", "fail", "ok2");

        Function<String, String> processor = k -> {
            if ("fail".equals(k)) {
                throw new IllegalStateException("boom");
            }
            return k.toUpperCase();
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

        Function<String, String> processor = k -> UUID.randomUUID().toString();

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

        Map<String, Integer> aNeighbors = new HashMap<>();
        aNeighbors.put("B", 1);
        aNeighbors.put("C", 4);
        graph.put("A", aNeighbors);

        Map<String, Integer> bNeighbors = new HashMap<>();
        bNeighbors.put("C", 2);
        bNeighbors.put("D", 5);
        graph.put("B", bNeighbors);

        Map<String, Integer> cNeighbors = new HashMap<>();
        cNeighbors.put("D", 1);
        graph.put("C", cNeighbors);

        graph.put("D", new HashMap<>());

        Map<String, Integer> distances = dataProcessor.findShortestPaths(graph, "A");

        assertNotNull(distances);
        assertEquals(0, distances.get("A").intValue());
        assertEquals(1, distances.get("B").intValue());
        assertEquals(3, distances.get("C").intValue());
        assertEquals(4, distances.get("D").intValue());
    }

    @Test
    @DisplayName("findShortestPaths should handle disconnected nodes with Integer.MAX_VALUE")
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