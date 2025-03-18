import click

from analysis.cli.cli import cli
from analysis.models.patch import Patch
from analysis.models.localization import Location, LocalizationReport, SystemLocations
from analysis.models.swe_bench import Split, Dataset
from analysis.models.data import Data


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
    """Compute the golden localization data."""
    click.echo(f"Computing golden localization data for SWE-bench {split.value}...")
    dataset = Dataset.from_split(split)
    click.echo(f"Found {len(dataset.instances)} instances.")

    gold_locations: dict[str, list[Location]] = {}
    errors: dict[str, Exception] = {}

    with click.progressbar(
        dataset.instances, label="Processing instances"
    ) as instances_bar:
        for instance in instances_bar:
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

    report = LocalizationReport(
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
    """Compute the leaderboard localization data."""
    click.echo(f"Computing localization data from leaderboard file {input}...")
    with open(input) as f:
        data = Data.model_validate_json(f.read())
    click.echo(f"Found {len(data.systems)} systems.")

    systems: list[SystemLocations] = []

    for system, evaluation in data.systems.items():
        system_locations = SystemLocations(system=system, locations={})
        errors: dict[str, Exception] = {}

        with click.progressbar(
            evaluation.predictions, label=f"Processing patches for {system}"
        ) as predictions_bar:
            for prediction in predictions_bar:
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

    report = LocalizationReport(systems=systems)

    with open(output, "w") as f:
        f.write(report.model_dump_json())
