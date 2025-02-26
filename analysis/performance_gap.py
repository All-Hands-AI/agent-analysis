from collections import Counter
from itertools import chain
from analysis.models.swe_bench import Evaluation, InstanceID

def top_performers(models: list[Evaluation], k: int = 3) -> list[Evaluation]:
    """Return the top performing models."""
    return sorted(
        models,
        key=lambda evaluation: len(evaluation.results.resolved),
        reverse=True,
    )[:k]

def unresolved_instances(
    source: Evaluation, targets: list[Evaluation], threshold: int | None = None
) -> set[InstanceID]:
    """Find instances not resolved by the source model but resolved by all target models.

    Setting the threshold lowers the number of targets that must resolve an instance for it to be considered resolved.
    """
    if threshold is None:
        threshold = len(targets)

    source_instance_ids = set(source.results.resolved)

    target_instance_id_counts = Counter(
        chain.from_iterable(t.results.resolved for t in targets)
    )
    target_instance_ids = set(
        [
            instance_id
            for (instance_id, count) in target_instance_id_counts.items()
            if count >= threshold
        ]
    )

    return target_instance_ids - source_instance_ids
