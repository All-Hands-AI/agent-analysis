"""
Download and store SWE-bench leadboard data locally.
"""

from __future__ import annotations

from logging import getLogger

from analysis.models.swe_bench import Evaluation, Split, Dataset, Instance
from analysis.models.patch import Patch
from difflib import get_close_matches
from pydantic import BaseModel

logger = getLogger(__name__)


class Data(BaseModel):
    dataset: Dataset
    systems: dict[str, Evaluation]

    @staticmethod
    def download(split: Split) -> Data:
        dataset = Dataset.from_split(split)
        entries = split.get_all_entries()
        systems: dict[str, Evaluation] = {}

        for entry in entries:
            try:
                system = Evaluation.from_github(split, entry)
                systems[entry] = system
            except ValueError as e:
                print(f"Skipping {entry}: {e}")
                continue

        return Data(dataset=dataset, systems=systems)

    def closest_system(self, system_name: str) -> str:
        """
        Get the system identifier closest to the provided name.
        """
        matches = get_close_matches(system_name, self.systems.keys(), n=1, cutoff=0.0)
        if not matches:
            raise ValueError(f"No system found for {system_name}")

        return matches[0]

    def get_instance(self, instance_id: str) -> Instance | None:
        """
        Get the instance with the provided identifier (if it can be found).
        """
        for instance in self.dataset.instances:
            if instance.instance_id == instance_id:
                return instance

    def get_dataset_patches(self) -> dict[str, Patch]:
        """
        Compute patches for all the instances in the dataset.
        """
        results: dict[str, Patch] = {}

        for instance in self.dataset.instances:
            try:
                patch = Patch.from_instance(instance)
                results[instance.instance_id] = patch
            except Exception as e:
                logger.warning(
                    f"Failed to compute gold patch for {instance.instance_id}: {e}"
                )

        return results

    def get_evaluation_patches(
        self, system: str, allowable_error_rate: float = 0.1
    ) -> dict[str, Patch]:
        """
        Compute patches for all the instances in the evaluation.

        Args:
            system: the system identifier.
            allowable_error_rate: the maximum fraction of instances that can fail to be
                parsed before an error is raised.

        Raises:
            KeyError: if the system is not found.
            ValueError: if the system has too many predictions or too few parseable patches.
        """
        evaluation = self.systems[system]

        # Check that the system doesn't have too many predictions.
        if len(evaluation.predictions) > len(self.dataset.instances):
            raise ValueError(
                f"Too many predictions for {system}: {len(evaluation.predictions)}"
            )

        allowable_errors = int(len(self.dataset.instances) * allowable_error_rate)
        actual_errors: int = 0

        results: dict[str, Patch] = {}
        for prediction in evaluation.predictions:
            try:
                instance = self.get_instance(prediction.instance_id)
                patch = Patch.from_github(
                    instance.repo, instance.base_commit, prediction.patch
                )
                results[prediction.instance_id] = patch
            except Exception as e:
                actual_errors += 1
                logger.warning(
                    f"Failed to compute generated patch for {system}/{prediction.instance_id}: {e}"
                )

            if actual_errors > allowable_errors:
                raise ValueError(
                    f"Too many errors for {system}: allowed {allowable_errors}"
                )

        return results
