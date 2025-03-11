from __future__ import annotations

from typing import Callable
from analysis.features.metrics.metrics import Metrics
from analysis.models.patch import Patch
from analysis.trajectory import is_read, is_write, get_location, Trajectory
from pydantic import Field

class LocalizationMetrics(Metrics):
    """Metrics for analyzing read/write behavior of an agent with respect to some tracked locations."""

    reads: int = Field(
        default=0, description="Number of reads of the tracked locations"
    )
    writes: int = Field(
        default=0, description="Number of writes to the tracked locations"
    )
    total_reads: int = Field(
        default=0,
        description="Total number of reads of tracked and untracked locations",
    )
    total_writes: int = Field(
        default=0,
        description="Total number of writes to tracked and untracked locations",
    )
    first_read: int | None = Field(
        default=None, description="Position of the first read of the tracked locations"
    )
    first_write: int | None = Field(
        default=None, description="Position of the first write to the tracked locations"
    )
    last_read: int | None = Field(
        default=None, description="Position of the last read of the tracked locations"
    )
    last_write: int | None = Field(
        default=None, description="Position of the last write to the tracked locations"
    )

    @staticmethod
    def from_trajectory(trajectory: Trajectory, is_tracked: Callable[[str], bool]) -> LocalizationMetrics:
        """Create localization metrics from a trajectory."""
        reads: list[int] = []
        writes: list[int] = []

        total_reads: int = 0
        total_writes: int = 0

        for index, step in enumerate(trajectory):
            # Track reads            
            if is_read(step):
                total_reads += 1
                if is_tracked(get_location(step)):
                    reads.append(index)

            # Track writes
            if is_write(step):
                total_writes += 1
                if is_tracked(get_location(step)):
                    writes.append(index)

        return LocalizationMetrics(
            reads=len(reads),
            writes=len(writes),
            total_reads=total_reads,
            total_writes=total_writes,
            first_read=reads[0] if reads else None,
            first_write=writes[0] if writes else None,
            last_read=reads[-1] if reads else None,
            last_write=writes[-1] if writes else None,
        )

def in_patch(location: str, patch: Patch) -> bool:
    """Check if a location is in a patch."""
    return any(location in file for file in patch.files.keys())

def is_reproduction_attempt(location: str, repo: str) -> bool:
    """Check if a location is a reproduction attempt."""
    if repo in location:
        return False
    
    return any(hint in location for hint in ["reproduce", "recreate", "test"])