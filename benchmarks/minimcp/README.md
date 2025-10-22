# MiniMCP · Benchmarks

Once you’ve set up a development environment as described in [CONTRIBUTING.md](../../CONTRIBUTING.md)
, you can run the benchmark scripts.

## Run Benchmarks

```bash
# Stdio
uv run python -m benchmarks.minimcp.macro.stdio_mcp_server_benchmark

# HTTP
uv run python -m benchmarks.minimcp.macro.http_mcp_server_benchmark
```

## Analyze Results

```bash
# Stdio
uv run python benchmarks/minimcp/analyze_results.py benchmarks/minimcp/reports/stdio_mcp_server_sync_benchmark_results.json

uv run python benchmarks/minimcp/analyze_results.py benchmarks/minimcp/reports/stdio_mcp_server_async_benchmark_results.json

# HTTP
uv run python benchmarks/minimcp/analyze_results.py benchmarks/minimcp/reports/http_mcp_server_async_benchmark_results.json

uv run python benchmarks/minimcp/analyze_results.py benchmarks/minimcp/reports/http_mcp_server_async_benchmark_results.json
```

## Generate Report

Provide the following prompt along with one of the results json file to an AI assistant to generate a comprehensive markdown report.

```text
I have ran a benchmark on MCP servers. Please analyze the benchmark result JSON file and generate a comprehensive
markdown report.

The report should include:

1. **Executive Summary**
   - High-level comparison of the servers
   - Key findings with percentage improvements
   - Resource efficiency comparison

2. **Benchmark Configuration**
   - Test environment details (date, platform, Python version, duration)
   - Load profiles table (rounds, iterations, concurrency, total requests)
   - Metrics tracked with descriptions

3. **Performance Comparison**
   - Response Time Analysis:
     * Visual comparison using block characters (▓) showing relative performance
     * Tables comparing mean response times across all loads
     * Key observations highlighting performance trends
     * P95 distribution analysis for tail latency
   - Throughput Analysis:
     * Tables comparing requests per second
     * Key observations on scaling behavior
     * Consistency analysis (standard deviation comparison)
   - Resource Usage Analysis:
     * CPU usage comparison
     * Memory usage comparison with insights

4. **Detailed Load Profile Results**
   - Separate section for each load type (Sequential, Light, Medium, Heavy)
   - Tables comparing all key metrics
   - Analysis paragraph highlighting notable differences

5. **Statistical Significance**
   - Outlier analysis with percentages
   - Notes on data quality and interpretation

6. **Performance Trends**
   - Scalability analysis showing response time scaling factors
   - Throughput scaling comparison
   - Visual representation of scaling behavior

7. **Recommendations**
   - Clear guidance on when to choose each server
   - Use cases for each option

8. **Conclusions**
   - Numbered list of key takeaways
   - Overall winner declaration with trophy emoji
   - Summary of improvements

9. **Appendix: Benchmark Methodology**
   - Test design details
   - Sample sizes
   - Statistical metrics definitions

Format Requirements:
- Use clear markdown with proper headers (## for main sections, ### for subsections)
- Include horizontal rules (---) between major sections
- Use tables for data comparison
- Add visual elements using block characters (▓) for response time and throughput comparisons
- Use checkmarks (✓), double checkmarks (✓✓), and emojis (🏆) for emphasis
- Include percentage improvements and absolute values
- Add "Key Observations" or "Key Insight" sections after important comparisons
- Make it easy to scan with bold text for important findings

Provide a downloadable report md file.
```
