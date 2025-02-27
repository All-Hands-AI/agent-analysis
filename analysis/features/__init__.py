from typing import Iterable
import pandas as pd

from analysis.models.patch import Patch
from analysis.models.swe_bench import Instance

from analysis.features.metrics import (
    CodeMetrics,
    TypeMetrics,
    ErrorMetrics,
    DependencyMetrics,
    PatchMetrics,
    InstanceMetrics,
    apply_metrics,
)

def compute_instance_features(instances: Iterable[Instance]) -> pd.DataFrame:
    """Compute features for a list of instances."""
    rows = []
    for instance in instances:
        try:
            patch = Patch.from_instance(instance)
        except Exception as e:
            print(f"Failed to compute metrics for instance {instance.instance_id}: {e}")
            continue

        # Compute the metrics that act over diffs
        metrics = apply_metrics(
            patch,
            {
                "code": CodeMetrics,
                "type": TypeMetrics,
                "error": ErrorMetrics,
                "dependency": DependencyMetrics,
            },
        )

        # Build a row, making sure to add metrics for the patch and instance structure
        row = pd.DataFrame(
            [
                {
                    **metrics,
                    **PatchMetrics.from_patch(patch).to_dict(prefix="patch"),
                    **InstanceMetrics.from_instance(instance).to_dict(
                        prefix="instance"
                    ),
                    "instance_id": instance.instance_id,
                }
            ]
        )
        rows.append(row)

    return pd.concat(rows)
