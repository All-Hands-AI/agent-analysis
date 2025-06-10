#!/usr/bin/env python3

import argparse
import json
import os
import toml
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any, Optional


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Count resolved instances across multiple trajectory files")
    parser.add_argument(
        "--trajectories", 
        nargs="+", 
        required=True,
        help="List of paths to trajectory directories or JSONL files"
    )
    parser.add_argument(
        "--split", 
        required=True,
        help="Output path for the TOML file containing instance IDs grouped by resolution counts"
    )
    parser.add_argument(
        "--split-size",
        type=int,
        default=50,
        help="Size of each representative split (default: 50)"
    )
    return parser.parse_args()


def process_trajectories(trajectory_paths: List[str]) -> Dict[str, int]:
    """
    Process multiple trajectory files and count resolved instances.
    
    Args:
        trajectory_paths: List of paths to trajectory directories or JSONL files
        
    Returns:
        Dictionary with instance_ids as keys and count of resolved=True as values
    """
    count_resolved = defaultdict(int)
    all_instance_ids = set()  # Track all instance IDs encountered
    processed_files = 0
    
    for path in trajectory_paths:
        # Check if path is a directory
        if os.path.isdir(path):
            # Look for output.jsonl in the directory
            jsonl_path = os.path.join(path, "output.jsonl")
            if not os.path.exists(jsonl_path):
                print(f"Warning: No output.jsonl found in directory: {path}")
                continue
            file_paths = [jsonl_path]
        else:
            # Treat as a direct file path
            file_paths = [path]
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            instance_id = data.get('instance_id')
                            
                            # Check if instance_id exists
                            if not instance_id:
                                # Try to get it from the instance object if available
                                instance = data.get('instance')
                                if instance and isinstance(instance, dict):
                                    instance_id = instance.get('instance_id')
                            
                            # Skip if we still don't have an instance_id
                            if not instance_id:
                                continue
                            
                            # Add to the set of all instance IDs
                            all_instance_ids.add(instance_id)
                                
                            # Check if report.resolved is True
                            report = data.get('report')
                            if report and isinstance(report, dict) and report.get('resolved') is True:
                                count_resolved[instance_id] += 1
                                
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
                processed_files += 1
            except FileNotFoundError:
                print(f"Warning: File not found: {file_path}")
                continue
    
    # Ensure all encountered instance IDs are in the dictionary (even with 0 count)
    result = dict(count_resolved)
    for instance_id in all_instance_ids:
        if instance_id not in result:
            result[instance_id] = 0
            
    return result, processed_files


def create_representative_split(count_resolved: Dict[str, int], split_size: int, split_index: int, 
                        used_ids: set = None) -> List[str]:
    """
    Create a representative split of instance IDs that maintains the same distribution of resolution counts.
    Each split contains unique IDs that don't appear in previous splits.
    
    Args:
        count_resolved: Dictionary with instance_ids as keys and count of resolved=True as values
        split_size: Size of the split
        split_index: Index of the split (used for deterministic sampling)
        used_ids: Set of instance IDs that have already been used in previous splits
        
    Returns:
        List of instance IDs in the representative split
    """
    # Initialize used_ids if not provided
    if used_ids is None:
        used_ids = set()
    
    # Group instance IDs by resolution count, excluding already used IDs
    grouped_by_count = defaultdict(list)
    available_count_resolved = {}
    
    for instance_id, count in count_resolved.items():
        if instance_id not in used_ids:
            grouped_by_count[count].append(instance_id)
            available_count_resolved[instance_id] = count
    
    # Calculate the distribution of resolution counts in the original dataset
    total_instances = len(count_resolved)
    original_count_distribution = {count: len([id for id in count_resolved if count_resolved[id] == count]) / total_instances 
                                  for count in set(count_resolved.values())}
    
    # Calculate how many instances to include from each resolution count based on original distribution
    instances_per_count = {count: max(1, int(split_size * percentage)) 
                          for count, percentage in original_count_distribution.items()}
    
    # Check if we have enough instances in each count category
    for count in list(instances_per_count.keys()):
        available = len(grouped_by_count[count])
        if available < instances_per_count[count]:
            instances_per_count[count] = available
    
    # Adjust to ensure we get as close as possible to split_size instances
    total_selected = sum(instances_per_count.values())
    
    # If we don't have enough instances, add more from categories that still have available instances
    if total_selected < split_size:
        # Sort counts by number of available instances (descending)
        counts_with_available = [(count, len(grouped_by_count[count]) - instances_per_count[count]) 
                               for count in instances_per_count 
                               if len(grouped_by_count[count]) > instances_per_count[count]]
        
        counts_with_available.sort(key=lambda x: x[1], reverse=True)
        
        for count, _ in counts_with_available:
            if total_selected >= split_size:
                break
            available = len(grouped_by_count[count]) - instances_per_count[count]
            to_add = min(available, split_size - total_selected)
            instances_per_count[count] += to_add
            total_selected += to_add
    
    # If we have too many instances, remove from the least common resolution counts
    elif total_selected > split_size:
        # Sort by original distribution (ascending)
        sorted_counts = sorted(original_count_distribution.items(), key=lambda x: x[1])
        
        for count, _ in sorted_counts:
            if total_selected <= split_size or instances_per_count.get(count, 0) <= 1:
                break
            instances_per_count[count] -= 1
            total_selected -= 1
    
    # Select instances from each resolution count
    selected_ids = []
    for count, num_to_select in instances_per_count.items():
        if num_to_select <= 0:
            continue
            
        # Sort for deterministic selection
        sorted_ids = sorted(grouped_by_count[count])
        
        # Use a deterministic sampling based on split_index
        if len(sorted_ids) <= num_to_select:
            selected_ids.extend(sorted_ids)
        else:
            # Use a deterministic sampling method
            np.random.seed(42 + split_index)  # Fixed seed + split_index for deterministic but different splits
            selected_indices = np.random.choice(len(sorted_ids), num_to_select, replace=False)
            selected_ids.extend([sorted_ids[i] for i in selected_indices])
    
    return sorted(selected_ids)


def save_as_toml(count_resolved: Dict[str, int], output_path: str, split_size: int) -> None:
    """
    Save the results as a TOML file with instance IDs grouped by resolution count.
    Creates representative splits with unique IDs across splits.
    
    Args:
        count_resolved: Dictionary with instance_ids as keys and count of resolved=True as values
        output_path: Path to save the TOML file
        split_size: Size of each representative split
    """
    # Group instance IDs by resolution count
    grouped_by_count = defaultdict(list)
    for instance_id, count in count_resolved.items():
        grouped_by_count[count].append(instance_id)
    
    # Sort instance IDs within each group for consistency
    for count in grouped_by_count:
        grouped_by_count[count].sort()
    
    # Calculate the distribution of resolution counts
    total_instances = len(count_resolved)
    count_distribution = {count: len(ids) / total_instances for count, ids in grouped_by_count.items()}
    
    # Create TOML content
    toml_content = ""
    
    # Add overall distribution information
    distribution_str = ", ".join([f"{count_distribution[count]*100:.1f}% of ids were resolved {count} times" 
                                 for count in sorted(count_distribution.keys())])
    toml_content += f"# {distribution_str}\n\n"
    
    # Add resolution count groups
    for count in sorted(grouped_by_count.keys()):
        toml_content += f"# resolved {count} times\n"
        toml_content += f"r{count}_selected_ids = {grouped_by_count[count]}\n\n"
    
    # Calculate number of representative splits
    num_splits = (total_instances + split_size - 1) // split_size  # Ceiling division
    num_splits = min(num_splits, 10)  # Limit to 10 splits maximum
    
    # Add overall distribution comment before representative splits section
    toml_content += f"# Parent distribution: {distribution_str}\n\n"
    
    # Create representative splits with unique IDs across splits
    used_ids = set()
    for i in range(num_splits):
        rep_split = create_representative_split(count_resolved, split_size, i, used_ids)
        
        # Update used_ids with the IDs in this split
        used_ids.update(rep_split)
        
        # Calculate the distribution in this split
        split_counts = defaultdict(int)
        for instance_id in rep_split:
            split_counts[count_resolved[instance_id]] += 1
        
        split_distribution = {count: split_counts[count] / len(rep_split) if len(rep_split) > 0 else 0 
                             for count in sorted(count_distribution.keys())}
        
        split_distribution_str = ", ".join([f"{split_distribution[count]*100:.1f}% of ids were resolved {count} times" 
                                          for count in sorted(split_distribution.keys())])
        
        # Add parent distribution for comparison
        toml_content += f"# Parent distribution: {distribution_str}\n"
        toml_content += f"# Split {i} distribution: {split_distribution_str}\n"
        toml_content += f"# Split of length {len(rep_split)}\n"
        toml_content += f"rep{i}_selected_ids = {rep_split}\n\n"
    
    # Write to file
    with open(output_path, 'w') as f:
        f.write(toml_content)


def main():
    args = parse_args()
    
    # Process trajectories and count resolved instances
    count_resolved, processed_files = process_trajectories(args.trajectories)
    
    # Save the results to the specified output path as TOML
    save_as_toml(count_resolved, args.split, args.split_size)
    
    print(f"Processed {len(args.trajectories)} trajectory directories/files")
    print(f"Successfully read {processed_files} JSONL files")
    print(f"Found {len(count_resolved)} unique instance IDs")
    print(f"Created representative splits of size {args.split_size}")
    print(f"Results saved to {args.split}")


if __name__ == "__main__":
    main()