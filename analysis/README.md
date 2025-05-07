# Analysis Module

This module provides tools for downloading, processing, and analyzing SWE-bench data and agent performance metrics.

## Command Line Interface

The analysis module provides a command-line interface with the following commands:

### Download SWE-bench Data

```bash
python -m analysis download [OPTIONS]

Options:
  --split TEXT     Dataset split to download (default: "verified")
  -o, --output TEXT    Output file path (default: "data.json")
```

Example:
```bash
# Download verified split
python -m analysis download

# Download specific split to custom location
python -m analysis download --split test --output test_data.json
```

### Compute Features

```bash
python -m analysis compute_features [OPTIONS]

Options:
  -i, --input TEXT     Input data file path (default: "data.json")
  -o, --output TEXT    Output CSV file path (default: "features.csv")
```

Example:
```bash
# Compute features using default files
python -m analysis compute_features

# Compute features with custom input/output
python -m analysis compute_features -i my_data.json -o my_features.csv
```

## Python API

### Performance Gap Analysis

The `performance_gap` module provides utilities for analyzing performance differences between models:

```python
from analysis.performance_gap import top_performers, unresolved_instances

# Get top performing models
top_models = top_performers(models, k=3)

# Find instances resolved by target models but not by source
gaps = unresolved_instances(source_model, target_models, threshold=2)
```

### Resource Usage Analysis

The `usage` module helps track and analyze resource usage:

```python
from analysis.usage import total_resource_usage, per_iteration_resource_usage

# Get total resource usage for an evaluation
total_usage = total_resource_usage(evaluation_output)

# Get resource usage per iteration
for usage in per_iteration_resource_usage(evaluation_output):
    print(f"Prompt tokens: {usage.prompt_tokens}")
    print(f"Completion tokens: {usage.completion_tokens}")
    print(f"Response latency: {usage.response_latency}")
```

## Features

The analysis toolkit computes various metrics for agent analysis:

- Code metrics (complexity, size, etc.)
- Dependency metrics
- Error metrics
- Instance metrics
- Patch metrics
- Type metrics

These metrics are computed automatically when running the `compute_features` command.

## Data Models

The module uses structured data models for:

- SWE-bench data and evaluations
- OpenHands evaluation outputs
- Patch analysis
- Resource usage tracking

These models ensure consistent data handling and analysis across the toolkit.