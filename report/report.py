#!/usr/bin/env python3
"""
Count the number of resolved instances and calculate average accumulated cost in an evaluation file.

Usage:
    python repott.py <jsonl_file>

This script analyzes a JSONL file containing SWEBench evaluation results and reports:
1. The number and percentage of resolved instances
2. Cost statistics for all instances
3. Cost statistics for resolved instances only
4. Cost statistics for unresolved instances only
"""

import sys
import json
from pathlib import Path
import statistics
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

from analysis.models.openhands import SWEBenchResult, SWEBenchTestResult, SWEBenchTestReport

def analyze_jsonl(filepath: str) -> Tuple[int, int, Dict[str, Any], int, int, int, Dict[str, Any]]:
    """
    Analyze resolved instances, accumulated costs, and durations in a JSONL file.
    
    Args:
        filepath: Path to the JSONL file
        
    Returns:
        Tuple containing:
        - Number of resolved instances
        - Total number of instances
        - Dictionary with cost statistics for all, resolved, and unresolved instances
        - Number of instances with "finish" action
        - Number of instances with both "finish" action and resolved status
        - Number of instances with "finish" action but not resolved
        - Dictionary with duration statistics for all, resolved, and unresolved instances
    """
    # Load the data directly from the JSONL file
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Parse each line as JSON
    results = []
    all_costs = []
    resolved_costs = []
    unresolved_costs = []
    all_durations = []
    resolved_durations = []
    unresolved_durations = []
    instance_ids = []
    instances_with_finish_action = set()
    instance_timestamps = {}
    
    for line in lines:
        data = json.loads(line)
        
        # Extract instance ID
        instance_id = data.get('instance_id', 'unknown')
        if instance_id not in instance_ids:
            instance_ids.append(instance_id)
        
        # Create a SWEBenchResult object
        result = SWEBenchResult(
            instance_id=instance_id,
            test_result=SWEBenchTestResult(
                report=SWEBenchTestReport(**data['report'])
            )
        )
        
        # Extract accumulated cost from metrics if available
        accumulated_cost = None
        if 'metrics' in data and data['metrics'] and 'accumulated_cost' in data['metrics']:
            accumulated_cost = data['metrics']['accumulated_cost']
            all_costs.append(accumulated_cost)
        
        # Track if this instance was resolved
        is_resolved = result.test_result.report.resolved
        
        # Check if history contains "action": "finish" and collect timestamps
        if 'history' in data and isinstance(data['history'], list):
            # Initialize timestamps list for this instance if not already present
            if instance_id not in instance_timestamps:
                instance_timestamps[instance_id] = []
                
            for entry in data['history']:
                if isinstance(entry, dict):
                    # Check for finish action
                    if entry.get('action') == 'finish':
                        instances_with_finish_action.add(instance_id)
                    
                    # Collect timestamp if available
                    if 'timestamp' in entry:
                        try:
                            # Parse timestamp (assuming ISO format)
                            timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                            instance_timestamps[instance_id].append(timestamp)
                        except (ValueError, TypeError):
                            # Skip invalid timestamps
                            pass
        
        # Add to results with cost information
        results.append((result, accumulated_cost, is_resolved))
        
        # Add cost to appropriate category
        if accumulated_cost is not None:
            if is_resolved:
                resolved_costs.append(accumulated_cost)
            else:
                unresolved_costs.append(accumulated_cost)
    
    # Count resolved instances
    resolved_count = sum(1 for _, _, is_resolved in results if is_resolved)
    finish_action_count = len(instances_with_finish_action)
    
    # Count instances with both finish action and resolved status
    resolved_instance_ids = set(result.instance_id for result, _, is_resolved in results if is_resolved)
    finish_and_resolved = len(instances_with_finish_action.intersection(resolved_instance_ids))
    finish_but_not_resolved = len(instances_with_finish_action - resolved_instance_ids)
    
    # Calculate durations for each instance
    for instance_id, timestamps in instance_timestamps.items():
        if timestamps:
            # Calculate duration in seconds
            earliest = min(timestamps)
            latest = max(timestamps)
            duration_seconds = (latest - earliest).total_seconds()
            
            # Add to all durations
            all_durations.append(duration_seconds)
            
            # Add to appropriate category based on resolution status
            is_resolved = any(result.test_result.report.resolved for result, _, _ in results 
                             if result.instance_id == instance_id)
            if is_resolved:
                resolved_durations.append(duration_seconds)
            else:
                unresolved_durations.append(duration_seconds)
    
    # Calculate cost statistics
    cost_stats = {
        'all': calculate_stats(all_costs) if all_costs else {},
        'resolved': calculate_stats(resolved_costs) if resolved_costs else {},
        'unresolved': calculate_stats(unresolved_costs) if unresolved_costs else {}
    }
    
    # Calculate duration statistics
    duration_stats = {
        'all': calculate_stats(all_durations) if all_durations else {},
        'resolved': calculate_stats(resolved_durations) if resolved_durations else {},
        'unresolved': calculate_stats(unresolved_durations) if unresolved_durations else {}
    }
    
    return resolved_count, len(instance_ids), cost_stats, finish_action_count, finish_and_resolved, finish_but_not_resolved, duration_stats

def calculate_stats(values: List[float]) -> Dict[str, Any]:
    """Calculate statistics for a list of values."""
    if not values:
        return {}
    
    return {
        'total': sum(values),
        'average': statistics.mean(values),
        'median': statistics.median(values),
        'min': min(values),
        'max': max(values),
        'count': len(values),
        'std_dev': statistics.stdev(values) if len(values) > 1 else 0
    }

def print_cost_stats(category: str, stats: Dict[str, Any]) -> None:
    """Print cost statistics in a formatted way."""
    if not stats:
        print(f"\nNo accumulated cost information available for {category} instances.")
        return
    
    print(f"\nAccumulated cost statistics ({category} {stats['count']} instances):")
    print(f"  Total cost: ${stats['total']:.6f}")
    print(f"  Average cost: ${stats['average']:.6f}")
    print(f"  Median cost: ${stats['median']:.6f}")
    print(f"  Min cost: ${stats['min']:.6f}")
    print(f"  Max cost: ${stats['max']:.6f}")
    print(f"  Standard deviation: ${stats['std_dev']:.6f}")

def print_duration_stats(category: str, stats: Dict[str, Any]) -> None:
    """Print duration statistics in a formatted way."""
    if not stats:
        print(f"\nNo duration information available for {category} instances.")
        return
    
    print(f"\nDuration statistics ({category} {stats['count']} instances):")
    print(f"  Average duration: {stats['average']:.2f} seconds ({stats['average']/60:.2f} minutes)")
    print(f"  Median duration: {stats['median']:.2f} seconds ({stats['median']/60:.2f} minutes)")
    print(f"  Min duration: {stats['min']:.2f} seconds ({stats['min']/60:.2f} minutes)")
    print(f"  Max duration: {stats['max']:.2f} seconds ({stats['max']/60:.2f} minutes)")
    print(f"  Standard deviation: {stats['std_dev']:.2f} seconds")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <jsonl_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    resolved_count, total_count, cost_stats, finish_action_count, finish_and_resolved, finish_but_not_resolved, duration_stats = analyze_jsonl(filepath)
    
    # Calculate metrics based on the definitions:
    # - Resolved instances (true positives): Instances that were actually solved correctly
    # - Finished instances: True positives + false positives (instances the agent thought it solved)
    # - Unfinished instances: False negatives + true negatives (instances the agent didn't attempt to solve)
    
    true_positives = finish_and_resolved  # Instances correctly solved (finished and resolved)
    false_positives = finish_but_not_resolved  # Instances the agent thought it solved but didn't (finished but not resolved)
    unfinished_count = total_count - finish_action_count  # Instances the agent didn't attempt to solve
    
    # Solution recall: What fraction of all instances were successfully solved
    # Recall = resolved_count / total_count
    solution_recall = resolved_count / total_count if total_count > 0 else 0
    
    # Solution precision: What fraction of the agent's solution attempts were successful
    # Precision = true_positives / (true_positives + false_positives)
    solution_precision = finish_and_resolved / finish_action_count if finish_action_count > 0 else 0
    
    # Calculate F1 score (F-measure): 2 * (precision * recall) / (precision + recall)
    # This is the harmonic mean of precision and recall
    f1_score = 2 * (solution_precision * solution_recall) / (solution_precision + solution_recall) if (solution_precision + solution_recall) > 0 else 0
    
    # Print results
    print(f"Resolved instances (true positives): {resolved_count}/{total_count} ({resolved_count/total_count:.1%})")
    print(f"Instances with 'finish' action (attempted solutions): {finish_action_count}/{total_count} ({finish_action_count/total_count:.1%})")
    print(f"Instances with 'finish' action and resolved (true positives): {finish_and_resolved}/{total_count} ({finish_and_resolved/total_count:.1%})")
    print(f"Instances with 'finish' action but not resolved (false positives): {finish_but_not_resolved}/{total_count} ({finish_but_not_resolved/total_count:.1%})")
    print(f"Instances without 'finish' action (unfinished): {unfinished_count}/{total_count} ({unfinished_count/total_count:.1%})")
    print()
    print(f"Solution recall: {solution_recall:.2%}")
    print(f"Solution precision: {solution_precision:.2%}")
    print(f"F1 score (F-measure): {f1_score:.2%}")
    
    # Print cost statistics for all categories
    print_cost_stats("all", cost_stats.get('all', {}))
    print_cost_stats("resolved", cost_stats.get('resolved', {}))
    print_cost_stats("unresolved", cost_stats.get('unresolved', {}))
    
    # Print duration statistics for all categories
    print_duration_stats("all", duration_stats.get('all', {}))
    print_duration_stats("resolved", duration_stats.get('resolved', {}))
    print_duration_stats("unresolved", duration_stats.get('unresolved', {}))
