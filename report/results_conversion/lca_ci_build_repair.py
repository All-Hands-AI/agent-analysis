#!/usr/bin/env python3

import argparse
import json
import os
from typing import Dict, List, Any


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Process trajectories and results files")
    parser.add_argument("--trajectories", required=True, help="Path to trajectories JSONL file")
    parser.add_argument("--results", required=True, help="Path to results JSON file")
    return parser.parse_args()


def load_results(results_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load results from JSON file."""
    with open(results_path, "r") as f:
        results = json.load(f)
    return results


def process_trajectories(trajectories_path: str, results: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Process trajectories and add report information."""
    # Extract instance IDs from resolved and unresolved instances
    resolved_ids = {instance["id"] for instance in results.get("resolved_instances", [])}
    unresolved_ids = {instance["id"] for instance in results.get("unresolved_instances", [])}
    
    processed_trajectories = []
    
    # Process each trajectory
    with open(trajectories_path, "r") as f:
        for line in f:
            trajectory = json.loads(line)
            instance_id = trajectory.get("instance_id")
            
            # Create or update report field
            if "report" not in trajectory:
                trajectory["report"] = {}
            
            # Set resolved status
            trajectory["report"]["resolved"] = instance_id in resolved_ids
            
            # Set error_eval status (false if in either resolved or unresolved)
            trajectory["report"]["error_eval"] = not (instance_id in resolved_ids or instance_id in unresolved_ids)
            
            processed_trajectories.append(trajectory)
    
    return processed_trajectories


def save_trajectories(trajectories: List[Dict[str, Any]], original_path: str):
    """Save processed trajectories to a new file."""
    # Create output filename based on original path
    dir_name = os.path.dirname(original_path)
    base_name = os.path.basename(original_path)
    name_without_ext = os.path.splitext(base_name)[0]
    output_path = os.path.join(dir_name, f"{name_without_ext}_with_report.jsonl")
    
    # Write trajectories to output file
    with open(output_path, "w") as f:
        for trajectory in trajectories:
            f.write(json.dumps(trajectory) + "\n")
    
    print(f"Processed trajectories saved to: {output_path}")


def main():
    """Main function."""
    args = parse_args()
    
    # Load results
    results = load_results(args.results)
    
    # Process trajectories
    processed_trajectories = process_trajectories(args.trajectories, results)
    
    # Save processed trajectories
    save_trajectories(processed_trajectories, args.trajectories)


if __name__ == "__main__":
    main()