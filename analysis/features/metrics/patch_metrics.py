from analysis.features.metrics.metrics import Metrics
from analysis.models.patch import Patch

class PatchMetrics(Metrics):
    number_of_files: int = 0
    number_of_lines: int = 0
    number_of_added_lines: int = 0
    number_of_removed_lines: int = 0

    @staticmethod
    def from_patch(patch: Patch) -> 'PatchMetrics':
        """Create patch metrics from a patch."""
        metrics = PatchMetrics()
        metrics.number_of_files = len(patch.diffs)
        metrics.number_of_lines = len(patch.patch.split("\n"))
        metrics.number_of_added_lines = len([line for line in patch.patch.split("\n") if line.startswith("+")])
        metrics.number_of_removed_lines = len([line for line in patch.patch.split("\n") if line.startswith("-")])
        return metrics