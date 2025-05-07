"""
Models representing the data structures produced by OpenHands during the evaluation pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable
import pandas as pd
from pydantic import BaseModel


class EvaluationMetadata(BaseModel):
    agent_class: str
    llm_config: LLMConfig
    max_iterations: int
    eval_output_dir: str
    start_time: str
    git_commit: str
    dataset: str | None = None
    data_split: str | None = None
    details: dict[str, Any] | None = None


class EvaluationOutput(BaseModel):
    # NOTE: User-specified
    instance_id: str
    # output of the evaluation
    # store anything that is needed for the score calculation
    test_result: dict[str, Any] | None = None

    instruction: str | None = None

    # Interaction info
    metadata: EvaluationMetadata | None = None
    # list[tuple[dict[str, Any], dict[str, Any]]] - for compatibility with the old format
    history: (
        list[dict[str, Any]] | list[tuple[dict[str, Any], dict[str, Any]]] | None
    ) = None
    metrics: dict[str, Any] | None = None
    error: str | None = None

    # Optionally save the input test instance
    instance: dict[str, Any] | None = None


class LLMConfig(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    embedding_model: str = "local"

    num_retries: int = 8
    retry_multiplier: float = 2
    retry_min_wait: int = 15
    retry_max_wait: int = 120
    timeout: int | None = None

    max_message_chars: int = 30_000  # maximum number of characters in an observation's content when sent to the llm
    temperature: float = 0.0
    top_p: float = 1.0

    max_input_tokens: int | None = None
    max_output_tokens: int | None = None

    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None

    disable_vision: bool | None = None
    caching_prompt: bool = True

    custom_tokenizer: str | None = None


class SWEBenchTestReport(BaseModel):
    empty_generation: bool
    resolved: bool
    failed_apply_patch: bool
    error_eval: bool
    test_timeout: bool


class SWEBenchTestResult(BaseModel):
    # git_patch: str
    report: SWEBenchTestReport


class SWEBenchResult(BaseModel):
    instance_id: str
    test_result: SWEBenchTestResult


class Evaluation(BaseModel):
    """
    Collection of metadata, generations, and test results for a single SWE-bench evaluation run.
    """
    
    filepath: Path
    """Path to the directory containing the evaluation files."""
    
    metadata: EvaluationMetadata
    """Metadata about the evaluation run."""

    output: list[EvaluationOutput]
    """List of evaluation outputs, one for each test instance."""
    
    results: list[SWEBenchResult]
    """List of test results, one for each test instance."""

    @staticmethod
    def from_filepath(
        filepath: Path,
        output_filename: str = "output.jsonl",
        results_filename: str = "output.swebench_eval.jsonl",
        metadata_filename: str = "metadata.json",
    ) -> Evaluation:
        """
        Load an evaluation from a directory containing the evaluation files.

        The directory, at a minimum, should contain a file for the metadata, the generated output, and the test results. In the standard OpenHands evaluation pipeline these are usually provided as top-level files in the evaluation directory.

        Args:
            filepath: Path to the directory containing the evaluation files.
            output_filename: Name of the file containing the generated output.
            results_filename: Name of the file containing the test results.
            metadata_filename: Name of the file containing the metadata.
        """
        with (filepath / metadata_filename).open() as f:
            metadata = EvaluationMetadata.model_validate_json(f.read())

        with (filepath / output_filename).open() as f:
            output = [
                EvaluationOutput.model_validate_json(line) for line in f.readlines()
            ]

        with (filepath / results_filename).open() as f:
            results = [
                SWEBenchResult.model_validate_json(line) for line in f.readlines()
            ]

        return Evaluation(
            filepath=filepath, metadata=metadata, output=output, results=results
        )

    def get_output(self, instance_id: str) -> EvaluationOutput:
        """
        Get the evaluation output for a specific instance ID.
        
        Raises:
            KeyError: if the instance ID is not found in the evaluation output.
        """
        for output in self.output:
            if output.instance_id == instance_id:
                return output

        raise KeyError

    def get_result(self, instance_id: str) -> SWEBenchResult:
        """
        Get the test result for a specific instance ID.
        
        Raises:
            KeyError: if the instance ID is not found in the test results.
        """
        for result in self.results:
            if result.instance_id == instance_id:
                return result

        raise KeyError

    def instance_ids(self) -> Iterable[str]:
        """
        Returns an iterable of all instance IDs with outputs in the evaluation.
        """
        for output in self.output:
            yield output.instance_id

    def experiment(self) -> str:
        """
        Returns the name of the experiment.

        Used as a short-hand for downstream analysis. Assumes the name of the experiment is the name of the directory containing the evaluation files.
        """
        return self.filepath.name

    def resolved(self) -> int:
        """
        Returns the number of instances that were resolved in the evaluation.
        """
        return sum(1 for result in self.results if result.test_result.report.resolved)

    def is_resolved(self, instance_id: str) -> bool:
        """
        Returns whether a specific instance ID was resolved in the evaluation.
        """
        try:
            result = self.get_result(instance_id)
            return result.test_result.report.resolved
        except KeyError:
            return False

    def to_dataframe(
        self,
        instance_callback: Callable[[EvaluationOutput, SWEBenchResult], dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Convert an evaluation to a pandas DataFrame.

        Requires a function that takes the evaluation output and test results and produces a
        dictionary of values. Each instance becomes a row in the resulting dataframe containing
        those values.
        """
        rows = []
        for instance_id in self.instance_ids():
            try:
                output = self.get_output(instance_id)
                result = self.get_result(instance_id)
            except KeyError:
                continue

            if not output.history:
                continue

            row = {
                "experiment": self.experiment(),
                "instance_id": instance_id,
                **instance_callback(output, result),
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def multi_to_dataframe(
        self,
        instance_callback: Callable[
            [EvaluationOutput, SWEBenchResult], Iterable[dict[str, Any]]
        ],
        post_callback: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
    ) -> pd.DataFrame:
        """
        Convert an evaluation to a pandas DataFrame.

        Requires a function that takes the evaluation output and test results and produces a
        sequence of dictionaries of values. This is useful for producing information per-step,
        as each item in the sequence will become a row in the resulting dataframe.

        Also supports an optional post-processing callback that takes the resulting dataframe
        and returns a modified version of it. You can use this to perform instance-specific
        transformations on the data.
        """
        tables = []
        for instance_id in self.instance_ids():
            try:
                output = self.get_output(instance_id)
                result = self.get_result(instance_id)

            except KeyError:
                continue

            if not output.history:
                continue

            rows = []
            for data in instance_callback(output, result):
                row = {
                    "experiment": self.experiment(),
                    "instance_id": instance_id,
                    **data,
                }
                rows.append(row)

            table = pd.DataFrame(rows)
            if post_callback is not None:
                updated_table = post_callback(table)
                tables.append(updated_table)

            else:
                tables.append(table)

        return pd.concat(tables)
