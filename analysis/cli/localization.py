from pathlib import Path
import click
import pandas as pd
from tqdm import tqdm

from analysis.cli.cli import cli
from analysis.features.metrics.localization_metrics import LocalizationMetrics
from analysis.models.patch import Patch
from analysis.models.localization import Location, LocalizationData, SystemLocations
from analysis.models.swe_bench import Split, Dataset
from analysis.models.data import Data
from analysis.models.openhands import EvaluationOutput


@cli.group()
def localization(): ...


@localization.command()
@click.option(
    "--split",
    type=Split,
    default="verified",
    callback=lambda _ctx, _, value: Split.from_str(value),
)
@click.option("--output", "-o", type=str, default="gold_localization_report.json")
def compute_gold(split: Split, output: str) -> None:
    """Compute localization data for the SWE-bench ground-truth patches."""
    click.echo(f"Computing golden localization data for SWE-bench {split.value}...")
    dataset = Dataset.from_split(split)
    click.echo(f"Found {len(dataset.instances)} instances.")

    gold_locations: dict[str, list[Location]] = {}
    errors: dict[str, Exception] = {}

    for instance in tqdm(dataset.instances, desc="Processing instances"):
        try:
            patch = Patch.from_instance(instance)
            locations = patch.locations
            gold_locations[instance.instance_id] = locations
        except Exception as e:
            errors[instance.instance_id] = e
            continue

    click.echo(f"Unable to process {len(errors)} instance(s).")
    for instance_id, error in errors.items():
        click.echo(f"Error processing instance {instance_id}: {error}")

    click.echo(f"Writing remaining {len(gold_locations)} instances to {output}...")

    report = LocalizationData(
        systems=[
            SystemLocations(
                system=f"swe-bench-gold-{split.value}",
                locations=gold_locations,
            )
        ]
    )

    with open(output, "w") as f:
        f.write(report.model_dump_json())


@localization.command()
@click.option("--input", "-i", type=str, default="data.json")
@click.option(
    "--output", "-o", type=str, default="leaderboard_localization_report.json"
)
@click.option("--error-rate", "-e", type=float, default=0.1)
def compute_leaderboard(input: str, output: str, error_rate: float) -> None:
    """Compute localization data for current SWE-bench leaderboard entries."""
    click.echo(f"Computing localization data from leaderboard file {input}...")
    with open(input) as f:
        data = Data.model_validate_json(f.read())
    click.echo(f"Found {len(data.systems)} systems.")

    systems: list[SystemLocations] = []

    for system, evaluation in tqdm(data.systems.items(), desc="Systems"):
        system_locations = SystemLocations(system=system, locations={})
        errors: dict[str, Exception] = {}

        for prediction in tqdm(
            evaluation.predictions, desc=f"Processing patches for {system}", leave=False
        ):
            try:
                instance = data.dataset[prediction.instance_id]
                patch = Patch.from_github(
                    instance.repo, instance.base_commit, prediction.patch
                )
                system_locations.locations[prediction.instance_id] = patch.locations
            except Exception as e:
                errors[prediction.instance_id] = e
                continue

            if len(errors) / len(evaluation.predictions) > error_rate:
                break

        if len(errors) / len(evaluation.predictions) > error_rate:
            click.echo(f"Too many errors for system {system} ({len(errors)} total).")

        systems.append(system_locations)

    click.echo(f"Writing {len(systems)} instances to {output}...")

    report = LocalizationData(systems=systems)

    with open(output, "w") as f:
        f.write(report.model_dump_json())


@localization.command()
@click.argument("input", type=str, nargs=-1)
@click.option(
    "--split",
    "-s",
    type=Split,
    default="verified",
    callback=lambda _ctx, _, value: Split.from_str(value),
    help="The split containing evaluation instances.",
)
@click.option(
    "--output", "-o", type=str, default="localization.json", help="Output file."
)
@click.option(
    "--recursive", "-r", is_flag=True, help="Recursively search for evaluations."
)
@click.option(
    "--error-rate", "-e", type=float, default=0.1, help="Max allowable error rate."
)
def compute(
    input: tuple[str, ...],
    split: Split,
    output: str,
    recursive: bool,
    error_rate: float,
) -> None:
    """Compute localization data for OpenHands evaluation directories.

    Searches for all trajectory files (output.jsonl) in directories in INPUT.
    """
    # Grab all the system evaluations to be found from the input (recursing if necessary)
    system_trajectory_paths: dict[str, Path] = {}

    worklist = list(input)
    while worklist:
        path = Path(worklist.pop())

        # If the trajectory path exists, add it to the system trajectory paths. We'll parse
        # it later.
        trajectory_path = path / "output.jsonl"
        if trajectory_path.exists():
            system_trajectory_paths[path.name] = trajectory_path

        # If the trajectory path doesn't exist and we're recursing, extend the worklist
        # with all subdirectories and we'll eventually repeat the process there.
        elif recursive:
            subdirs = [path / subpath for subpath in path.iterdir() if subpath.is_dir()]
            worklist.extend(subdirs)

    click.echo(f"Found {len(system_trajectory_paths)} system trajectories.")

    dataset = Dataset.from_split(split)

    systems: list[SystemLocations] = []

    for system, path in tqdm(system_trajectory_paths.items(), desc="Systems"):
        with path.open() as f:
            outputs = [
                EvaluationOutput.model_validate_json(line) for line in f.readlines()
            ]

        system_locations = SystemLocations(system=system, locations={})
        errors: dict[str, Exception] = {}

        for output in tqdm(
            outputs, desc=f"Processing patches for {system}", leave=False
        ):
            try:
                instance = dataset[output.instance_id]
                patch_source = output.test_result["git_patch"]
                patch = Patch.from_github(
                    instance.repo, instance.base_commit, patch_source
                )
                system_locations.locations[output.instance_id] = patch.locations

            except Exception as e:
                errors[output.instance_id] = e
                continue

            if len(errors) / len(outputs) > error_rate:
                break

        if len(errors) / len(outputs) > error_rate:
            click.echo(f"Too many errors for system {system} ({len(errors)} total).")

        systems.append(system_locations)

    report = LocalizationData(systems=systems)

    with open(output, "w") as f:
        f.write(report.model_dump_json())


@localization.command()
@click.argument("input", type=str, nargs=-1)
@click.option(
    "--output", "-o", type=str, default="localization.csv", help="Output file."
)
@click.option("--ground-truth", "-g", type=str, help="Ground truth system identifier.")
def report(input: tuple[str, ...], output: str, ground_truth: str) -> None:
    """Generate a CSV report containing localization metrics for all systems in INPUT."""
    # Start by loading the data. Load each data blob listed in INPUT and then flatten
    # the systems into a single dictionary.
    systems: dict[str, SystemLocations] = {}

    for path in input:
        with open(path, "r") as f:
            data = LocalizationData.model_validate_json(f.read())

        for system_locations in data.systems:
            systems[system_locations.system] = system_locations

    click.echo(f"Found {len(systems)} systems.")

    # Find the ground truth system. This must exist or we can't compute anything else.
    assert ground_truth in systems, f"Ground truth system {ground_truth} not found."
    ground_truth_system_locations = systems[ground_truth]

    rows = []
    for system, system_locations in tqdm(systems.items(), desc="Systems"):
        if systems == ground_truth:
            continue

        for instance_id, locations in system_locations.locations.items():
            metrics = LocalizationMetrics.from_locations(
                locations, ground_truth_system_locations.locations[instance_id]
            )

            rows.append(
                {
                    "system": system,
                    "instance_id": instance_id,
                    "file_match": metrics.file_match,
                    "function_match": metrics.function_match,
                    "class_match": metrics.class_match,
                    "file_precision": metrics.file_precision,
                    "function_precision": metrics.function_precision,
                    "class_precision": metrics.class_precision,
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
