from pathlib import Path
import click

from analysis.models.swe_bench import Split
from analysis.models.data import Data
from analysis.features import compute_instance_features, compute_localization_metrics

@click.group()
def cli(): ...


@cli.command()
@click.option(
    "--split",
    type=Split,
    default="verified",
    callback=lambda _ctx, _, value: Split.from_str(value),
)
@click.option("--output", "-o", type=str, default="data.json")
def download(split: Split, output: str) -> None:
    """Download and store SWE-bench data locally."""
    data = Data.download(split)
    with open(output, "w") as f:
        f.write(data.model_dump_json())

    # Compute size of downloaded file
    file_size = Path(output).stat().st_size
    click.echo(f"Downloaded {file_size} bytes to {output}")

@cli.command()
@click.option("--input", "-i", type=str, default="data.json")
@click.option("--output", "-o", type=str, default="features.csv")
def compute_features(input: str, output: str) -> None:
    """Compute features for the downloaded data."""
    with open(input) as f:
        data = Data.model_validate_json(f.read())

    df = compute_instance_features(data.dataset.instances)
    df.to_csv(output, index=False)

@cli.command()
@click.option("--input", "-i", type=str, default="data.json")
@click.option("--output", "-o", type=str, default="localization.csv")
@click.option("--error-rate", type=float, default=0.1)
def compute_localization(input: str, output: str, error_rate: float) -> None:
    """Compute localization scores for the data."""
    with open(input) as f:
        data = Data.model_validate_json(f.read())

    df = compute_localization_metrics(data, allowable_error_rate=error_rate)
    df.to_csv(output, index=False)

if __name__ == "__main__":
    cli()
