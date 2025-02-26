from typing import Type

from analysis.features.metrics.metrics import Metrics
from analysis.models.patch import Patch

from analysis.features.metrics.code_metrics import CodeMetrics
from analysis.features.metrics.dependency_metrics import DependencyMetrics
from analysis.features.metrics.error_metrics import ErrorMetrics
from analysis.features.metrics.instance_metrics import InstanceMetrics
from analysis.features.metrics.patch_metrics import PatchMetrics
from analysis.features.metrics.type_metrics import TypeMetrics

def apply_metrics(patch: Patch, metrics: dict[str, Type[Metrics]]) -> dict[str, int | float]:
    """Apply the provided metrics to a patch.
    
    Produces a dictionary whose entries correspond to each metric:
    1. Before the patch was applied,
    2. After the patch was applied, and
    3. The difference between the two.
    """
    results = {}
    for metric_identifier, metric in metrics.items():
        metrics_before = metric()
        metrics_after = metric()
        
        for diff in patch.files.values():
            metrics_before += metric.from_str(diff.before)
            metrics_after += metric.from_str(diff.after)

        metrics_diff = metrics_after - metrics_before
        results.update(
            **metrics_before.to_dict(prefix=metric_identifier, suffix="before"),
            **metrics_after.to_dict(prefix=metric_identifier, suffix="after"),
            **metrics_diff.to_dict(prefix=metric_identifier, suffix="diff")
        )
    return results

__all__ = [
    "apply_metrics",
    "Metrics",
    "CodeMetrics",
    "DependencyMetrics",
    "ErrorMetrics",
    "InstanceMetrics",
    "PatchMetrics",
    "TypeMetrics"
]