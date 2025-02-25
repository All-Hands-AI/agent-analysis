"""
Models for representing SWE-bench evaluation results.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime
import ast

import yaml
import requests

import datasets  # type: ignore
from pydantic import BaseModel, HttpUrl, AnyUrl, field_validator, Field


InstanceID = str
"""
Type alias for instance identifiers.
"""


class Split(str, Enum):
    """
    Collection of SWE-bench problem instances being considered.
    """

    LITE = "lite"
    TEST = "test"
    VERIFIED = "verified"

    @staticmethod
    def from_str(value: str) -> Split:
        """
        Get a split from a string.

        Raises:
            ValueError: if the string does not correspond to a valid split.
        """
        try:
            return Split[value.upper()]
        except KeyError as e:
            raise ValueError(f"{value} is not a valid split.") from e

    @property
    def dataset_identifier(self) -> str:
        """
        Identifier (compatible with `datasets`) containing the problem instances given by the split.
        """
        dataset_ids = {
            Split.LITE: "princeton-nlp/SWE-bench_Lite",
            Split.TEST: "princeton-nlp/SWE-bench",
            Split.VERIFIED: "princeton-nlp/SWE-bench_Verified",
        }
        return dataset_ids[self]
    
    def get_all_entries(self, timeout: int = 100) -> list[str]:
        """
        Get the list of all leaderboard entries for the split.

        Requires accessing the GitHub API: calling this function too frequently may result in rate limiting.
        """
        results: list[str] = []

        url = f"https://api.github.com/repos/swe-bench/experiments/contents/evaluation/{self.value}"
        request = requests.get(url, timeout=timeout)

        match request.status_code:
            case 200:
                for entry in request.json():
                    if entry["type"] == "dir":
                        results.append(entry["name"])

            case 408:
                raise ValueError(f"Request timed out after {timeout} seconds.")

            case _:
                raise ValueError(f"Unknown status code {request.status_code}.")

        return results


class Prediction(BaseModel, populate_by_name=True):
    """
    The per-instance output of a model.
    """

    instance_id: InstanceID
    """
    Identifier for the problem instance being solved.
    """

    patch: str | None = Field(alias="model_patch")
    """
    Git patch produced by the model.
    """

    name_or_path: str | None = Field(alias="model_name_or_path")
    """
    Name or path to the model used for prediction.
    """

class Results(BaseModel):
    """
    Summarized results of a leaderboard entry.
    """

    no_generation: list[InstanceID] = Field(default_factory=list)
    """
    Instance identifiers for which the model generated no patch.
    """

    no_logs: list[InstanceID] = Field(default_factory=list)
    """
    Instance identifiers for which the evaluation harness produced no logs.
    """

    resolved: list[InstanceID] = Field(default_factory=list)
    """
    Instance identifiers for all issues resolved by the model.
    """

    def is_resolved(self, instance_id: InstanceID) -> bool:
        """
        Check if an instance is resolved.
        """
        return instance_id in self.resolved


class Metadata(BaseModel):
    """
    Metadata about the leaderboard entry.
    """

    name: str
    """
    Name of the model used.
    """

    oss: bool
    """
    Whether the model is open-source or not.
    """

    verified: bool
    """
    Whether the results have been verified by SWE-bench leaderboard maintainers.
    """

    site: HttpUrl | None = None
    """
    URL for the model site.
    """

    logs: AnyUrl | None = None
    """
    S3 identifier for build/test logs.
    """

    trajs: AnyUrl | None = None
    """
    S3 identifier for model trajectories.
    """


def get_gh_file(split: Split, entry: str, path: str, timeout: int = 100) -> str:
    """
    Get a file from the SWE-bench Github repository.

    Args:
        split (Split): The split of the leaderboard entry containing the file.

        entry (str): The name of the leaderboard entry containing the file.

        path (str): Path to the file.

        timeout (int, default=100): Timeout for the HTTP request.

    Raises:
        ValueError: if the file cannot be found before the timeout.
    """
    GH_URL = "https://raw.githubusercontent.com"  # pylint: disable=invalid-name
    EVAL_DIR = "swe-bench/experiments/refs/heads/main/evaluation"  # pylint: disable=invalid-name

    request = requests.get(
        f"{GH_URL}/{EVAL_DIR}/{split.value}/{entry}/{path}",
        timeout=timeout,
    )

    match request.status_code:
        case 200:
            return request.text.strip()
        case 404:
            raise ValueError(
                f"Cannot find {split.value}/{entry}/{path} in the evaluation folder."
            )
        case 408:
            raise ValueError(f"Request timed out after {timeout} seconds.")
        case _:
            raise ValueError(f"Unexpected status code {request.status_code}.")


class Evaluation(BaseModel):
    """
    Summary of a model's evaluation on a SWE-bench problem set.
    """

    split: Split
    """
    The problem split being evaluated.
    """

    predictions: list[Prediction]
    """
    A list of predictions made by the model.
    """

    results: Results
    """
    Results summarizing prediction performance.
    """

    metadata: Metadata
    """
    Metadata about the leaderboard entry.
    """

    @staticmethod
    def from_github(split: Split, entry: str) -> Evaluation:
        """
        Generate an evaluation directly from the data on GitHub.
        """

        predictions = [
            Prediction.model_validate_json(line)
            for line in get_gh_file(split, entry, "all_preds.jsonl").split("\n")
            if line
        ]

        results = Results.model_validate_json(
            get_gh_file(split, entry, "results/results.json")
        )

        metadata = Metadata.model_validate(
            yaml.safe_load(get_gh_file(split, entry, "metadata.yaml"))
        )

        return Evaluation(
            split=split, predictions=predictions, results=results, metadata=metadata
        )


class Dataset(BaseModel):
    """
    Collection of problem instances.
    """

    split: Split
    """
    Split identifying the subset of problem instances.
    """

    instances: list[Instance]
    """
    Problem instances in the dataset.
    """

    @staticmethod
    def from_split(split: Split) -> Dataset:
        """
        Load the collection of problem instances from the indicated split.
        """
        data = datasets.load_dataset(split.dataset_identifier, split="test")
        return Dataset(
            split=split, instances=[Instance.model_validate(row) for row in data]
        )


class Instance(BaseModel, populate_by_name=True):
    """
    SWE-bench problem instance scraped from real-world fixes.
    """

    repo: str
    """
    The repository the problem instance originates from.
    """

    instance_id: InstanceID
    """
    Unique identifier created from the `repo` and pull number.
    """

    base_commit: str
    """
    The commit ID that the original PR was applied on top of.
    """

    patch: str
    """
    Reference solution to the problem, extracted from the original PR's changes.
    """

    test_patch: str
    """
    `.patch`-styled string with unseen tests checking if the problem was solved.
    """

    problem_statement: str
    """
    Natural language description of the desired changes to the code base.
    """

    hints_text: str
    """
    Natural language suggestion for how to solve the problem.
    """

    created_at: datetime
    """
    When the source PR was first created (not merged).
    """

    version: str
    """
    Release version (w.r.t. `repo`) during which the source PR was created.
    """

    fail_to_pass: list[str] = Field(alias="FAIL_TO_PASS")
    """
    List of tests that must change in status from "fail" to "pass" for a solution to count.
    """

    pass_to_pass: list[str] = Field(alias="PASS_TO_PASS")
    """
    List of tests that start passing and must continute to pass for a solution to count.
    """

    environment_setup_commit: str
    """
    Base commit at which to install necessary dependencies for running problem.
    """

    @field_validator("fail_to_pass", "pass_to_pass", mode="before")
    @classmethod
    def validate_to_pass_lists(cls, value: str | list[str]) -> list[str]:
        """
        Validation that converts string represntation of a list to a list.
        """
        if isinstance(value, str):
            return ast.literal_eval(value)

        return value