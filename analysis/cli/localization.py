import click

from analysis.cli.cli import cli
from analysis.models.patch import Patch
from analysis.models.localization import Location, LocalizationReport
from analysis.models.swe_bench import Split, Dataset


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
    
    with click.progressbar(dataset.instances, label="Processing instances") as instances:
        for instance in instances:
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
        system=f"swe-bench-gold-{split.value}",
        locations=gold_locations,
    )

    with open(output, "w") as f:
        f.write(report.model_dump_json())
