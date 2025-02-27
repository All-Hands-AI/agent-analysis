"""
Utility functions for manipulating OpenHands trajectories.
"""
from typing import Any

Step = dict[str, Any]
Trajectory = list[Step]

def is_read(step: Step) -> bool:
    """Check if a step is a read."""
    return "read" in step.get("action", "")

def is_write(step: Step) -> bool:
    """Check if a step is a write."""
    return "edit" in step.get("observation", "")

def get_location(step: Step) -> str:
    """Get the location of a step."""
    return step["message"].split(" ")[-1]