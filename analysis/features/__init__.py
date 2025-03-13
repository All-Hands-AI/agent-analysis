from typing import Iterable
import pandas as pd

from analysis.features.metrics.localization_metrics import LocalizationMetrics
from analysis.models.data import Data
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


def compute_localization_metrics(
    data: Data, allowable_error_rate: float = 0.1
) -> pd.DataFrame:
    """
    Compute localization metrics for all systems and instances in the provided data.

    This computation can take a long time and involves downloading a large number of
    files from GitHub.
    """
    gold_patches = data.get_dataset_patches()

    rows = []

    for system, evaluation in data.systems.items():
        # Compute the patch objects for each prediction in the system. Not all systems
        # support this kind of analysis -- some may have too many predictions, some may
        # have errors accessing the underlying files, etc.
        try:
            generated_patches = data.get_evaluation_patches(
                system, allowable_error_rate=allowable_error_rate
            )

        except ValueError:
            continue

        for prediction in evaluation.predictions:
            # Even for systems that have generated patches, we may not have access to all
            # the patch objects. This usually happens when the recorded patch is not able
            # to be parsed by unidiff.
            try:
                gold_patch = gold_patches[prediction.instance_id]
                generated_patch = generated_patches[prediction.instance_id]
            except KeyError:
                continue

            # Given the patches, we can compute the localization metrics. But this requires
            # parsing the underlying source of the patches, which may not actually be
            # well-formed Python.
            try:
                metrics = LocalizationMetrics.from_patch(gold_patch, generated_patch)
            except SyntaxError:
                continue

            rows.append(
                {
                    "system": system,
                    "instance_id": prediction.instance_id,
                    "patch": prediction.patch,
                    "resolved": prediction.instance_id in evaluation.results.resolved,
                    "missing_files": len(generated_patch.missing_files),
                    **metrics.model_dump(),
                }
            )

    return pd.DataFrame(rows)
