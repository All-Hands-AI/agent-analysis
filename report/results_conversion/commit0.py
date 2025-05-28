#!/usr/bin/env python3

import argparse
import json
import os
from typing import Dict, List, Any


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Process trajectories file for commit0 data")
    parser.add_argument("--trajectories", required=True, help="Path to trajectories JSONL file")
    return parser.parse_args()


def process_trajectories(trajectories_path: str) -> List[Dict[str, Any]]:
    """Process trajectories and add report information based on test_result.eval_result.passed."""
    processed_trajectories = []
    
    # Process each trajectory
    with open(trajectories_path, "r") as f:
        for line in f:
            trajectory = json.loads(line)
            
            # Create or update report field
            if "report" not in trajectory:
                trajectory["report"] = {}
            
            # Check if test_result.eval_result.passed is exactly 1
            passed = False
            if "test_result" in trajectory and "eval_result" in trajectory["test_result"]:
                if "passed" in trajectory["test_result"]["eval_result"]:
                    passed = trajectory["test_result"]["eval_result"]["passed"] == 1
            
            # Set resolved status
            trajectory["report"]["resolved"] = passed
            trajectory["report"]["empty_generation"] = False
            trajectory["report"]["error_eval"] = False
            trajectory["report"]["test_timeout"] = False
            trajectory["report"]["failed_apply_patch"] = False
            
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
    
    # Process trajectories
    processed_trajectories = process_trajectories(args.trajectories)
    
    # Save processed trajectories
    save_trajectories(processed_trajectories, args.trajectories)


if __name__ == "__main__":
    main()
