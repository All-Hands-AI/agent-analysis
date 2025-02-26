"""
Download and store SWE-bench leadboard data locally.
"""
from __future__ import annotations

from analysis.models.swe_bench import Evaluation, Split, Dataset, Instance
from difflib import get_close_matches
from pydantic import BaseModel

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
        for instance in self.dataset.instances:
            if instance.instance_id == instance_id:
                return instance