#!/usr/bin/env python3

import argparse
import json
import os
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
        help="Output path for the JSON file containing instance resolution counts"
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


def main():
    args = parse_args()
    
    # Process trajectories and count resolved instances
    count_resolved, processed_files = process_trajectories(args.trajectories)
    
    # Save the results to the specified output path
    with open(args.split, 'w') as f:
        json.dump(count_resolved, f, indent=2)
    
    print(f"Processed {len(args.trajectories)} trajectory directories/files")
    print(f"Successfully read {processed_files} JSONL files")
    print(f"Found {len(count_resolved)} unique instance IDs")
    print(f"Results saved to {args.split}")


if __name__ == "__main__":
    main()