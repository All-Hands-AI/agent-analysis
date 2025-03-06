# Agent Analysis

A comprehensive toolkit for analyzing Software Engineering (SWE) agents, focusing on performance evaluation, feature analysis, and benchmarking.

## Overview

This project provides tools and utilities for:
- Analyzing agent performance on software engineering tasks
- Computing various metrics (code, dependency, error, instance, patch, type)
- Evaluating performance gaps between different agent implementations
- Processing and analyzing data from OpenHands and SWE-bench

## Project Structure

- `analysis/`: Core analysis modules
  - `features/metrics/`: Various metric implementations for agent analysis
  - `models/`: Data models for OpenHands and SWE-bench
  - `performance_gap.py`: Performance gap analysis utilities
  - `usage.py`: Usage analysis tools

- `notebooks/`: Jupyter notebooks for analysis and visualization
  - `condenser_results.ipynb`: Analysis of condenser results
  - `localization_metrics.ipynb`: Metrics for code localization
  - `performance_gap.ipynb`: Performance gap analysis

## Requirements

- Python ≥ 3.12
- Dependencies are managed through Poetry

## Installation

1. Ensure you have Poetry installed
2. Clone this repository
3. Run `poetry install` to install dependencies

## Usage

The toolkit can be used either through its Python modules or via the provided Jupyter notebooks for interactive analysis.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
