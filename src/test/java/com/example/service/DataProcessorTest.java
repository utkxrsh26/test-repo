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

        assertEquals(Arrays.asList(6), even);
        assertEquals(Arrays.asList(5, 7), odd);
    }

    @Test
    @DisplayName("processDataPipeline should remove nulls and apply distinct and limit per group")
    void testProcessDataPipeline_DistinctAndLimit() {
        List<String> data = new ArrayList<>();
        for (int i = 0; i < 150; i++) {
            data.add("a" + (i % 3)); // a0, a1, a2 repeated
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
        List<String> groupList = result.get("group");
        assertNotNull(groupList);

        // distinct should reduce to 3 values: a0, a1, a2
        assertEquals(3, groupList.size());
        assertTrue(groupList.contains("a0"));
        assertTrue(groupList.contains("a1"));
        assertTrue(groupList.contains("a2"));
    }

    // ----------------------------------------------------------------------
    // calculateStatistics / StatisticalResult tests
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

        assertEquals(3.0, result.getMean(), 0.0001);
        assertEquals(3.0, result.getMedian(), 0.0001);
        assertEquals(2.0, result.getQ1(), 0.0001);
        assertEquals(4.0, result.getQ3(), 0.0001);

        double expectedVariance = (4 + 1 + 0 + 1 + 4) / 5.0;
        double expectedStdDev = Math.sqrt(expectedVariance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        assertNotNull(result.getOutliers());
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should compute correct statistics for even-sized list")
    void testCalculateStatistics_EvenSizedList() {
        List<Double> values = Arrays.asList(10.0, 20.0, 30.0, 40.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertEquals(25.0, result.getMean(), 0.0001);
        assertEquals(25.0, result.getMedian(), 0.0001);
        assertEquals(20.0, result.getQ1(), 0.0001);
        assertEquals(40.0, result.getQ3(), 0.0001);

        double expectedVariance =
                (Math.pow(10 - 25, 2) +
                 Math.pow(20 - 25, 2) +
                 Math.pow(30 - 25, 2) +
                 Math.pow(40 - 25, 2)) / 4.0;
        double expectedStdDev = Math.sqrt(expectedVariance);
        assertEquals(expectedStdDev, result.getStandardDeviation(), 0.0001);

        assertNotNull(result.getOutliers());
        assertTrue(result.getOutliers().isEmpty());
    }

    @Test
    @DisplayName("calculateStatistics should detect outliers using IQR method")
    void testCalculateStatistics_Outliers() {
        List<Double> values = Arrays.asList(10.0, 12.0, 11.0, 13.0, 12.5, 100.0);

        DataProcessor.StatisticalResult result = dataProcessor.calculateStatistics(values);

        assertNotNull(result.getOutliers());
        assertEquals(1, result.getOutliers().size());
        assertEquals(100.0, result.getOutliers().get(0), 0.0001);
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
    @DisplayName("processInParallel should propagate exceptions from processor")
    void testProcessInParallel_ExceptionPropagation() {
        List<String> keys = Arrays.asList("ok", "fail", "ok2");

        Function<String, Integer> processor = key -> {
            if ("fail".equals(key)) {
                throw new IllegalStateException("Failure for key: " + key);
            }
            return key.length();
        };

        CompletableFuture<Map<String, Integer>> future =
                dataProcessor.<Integer>processInParallel(keys, processor);

        assertNotNull(future);
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
        assertEquals(4, result.get("same"));
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

    // ----------------------------------------------------------------------
    // StatisticalResult immutability tests
    // ----------------------------------------------------------------------

    @Test
    @DisplayName("StatisticalResult getters should return correct values and be immutable")
    void testStatisticalResult_GettersAndImmutability() {
        List<Double> outliers = new ArrayList<>();
        outliers.add(100.0);
        outliers.add(200.0);

        DataProcessor.StatisticalResult result =
                new DataProcessor.StatisticalResult(10.0, 11.0, 9.0, 12.0, 1.5, outliers);

        assertEquals(10.0, result.getMean(), 0.0001);
        assertEquals(11.0, result.getMedian(), 0.0001);
        assertEquals(9.0, result.getQ1(), 0.0001);
        assertEquals(12.0, result.getQ3(), 0.0001);
        assertEquals(1.5, result.getStandardDeviation(), 0.0001);

        List<Double> returnedOutliers = result.getOutliers();
        assertEquals(2, returnedOutliers.size());
        assertEquals(100.0, returnedOutliers.get(0), 0.0001);
        assertEquals(200.0, returnedOutliers.get(1), 0.0001);

        assertThrows(UnsupportedOperationException.class, () -> returnedOutliers.add(300.0));
        outliers.add(300.0);
        assertEquals(2, result.getOutliers().size());
    }
}