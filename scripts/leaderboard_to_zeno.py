"""
Convert the current SWE-bench leaderboard to a Zeno project.
"""

from datetime import datetime

import pandas as pd
import click
import zeno_client

from analysis.models.swe_bench import Split, Dataset, Evaluation


@click.command()
@click.option(
    "--split",
    type=click.Choice(["lite", "verified", "test"]),
    default="verified",
    callback=lambda _ctx, _param, value: Split.from_str(value),
)
@click.option("--zeno-api-key", type=str, envvar="ZENO_API_KEY")
@click.option("--top-n", type=int, default=None, help="Only include top N systems")
def main(split: Split, zeno_api_key: str | None, top_n: int | None) -> None:
    """
    Convert the current leaderboard entries to a Zeno project.
    """
    # Build the Zeno client.
    assert zeno_api_key, "No Zeno API key found."
    viz_client = zeno_client.ZenoClient(zeno_api_key)

    # Create a new project.
    current_time = datetime.now()
    viz_project = viz_client.create_project(
        name="SWE-bench Leaderboard",
        view={
            "data": {"type": "markdown"},
            "label": {"type": "text"},
            "output": {
                "type": "vstack",
                "keys": {
                    "status": {"type": "text", "label": "Status"},
                    "patch": {"type": "code"},
                }
            },
        },
        description=f"SWE-bench leaderboard (as of {current_time}) performance analysis, by entry.",
        public=True,
        metrics=[
            zeno_client.ZenoMetric(name="resolved", type="mean", columns=["resolved"])
        ],
    )

    # Get entries for the split first to count resolutions
    entries = split.get_all_entries()
    
    # Track resolution counts per instance
    resolution_counts = {}
    
    # First pass to count resolutions
    for entry in entries:
        try:
            system = Evaluation.from_github(split, entry)
            for prediction in system.predictions:
                instance_id = prediction.instance_id
                if system.results.is_resolved(instance_id):
                    resolution_counts[instance_id] = resolution_counts.get(instance_id, 0) + 1
        except ValueError as e:
            print(f"Skipping {entry} during counting: {e}")
            continue

    # Build and upload the dataset with resolution counts
    dataset = Dataset.from_split(split)
    viz_project.upload_dataset(
        pd.DataFrame([{
            'instance_id': instance.instance_id,
            'problem_statement': instance.problem_statement,
            'repo': instance.repo,
            'base_commit': instance.base_commit,
            'times_resolved': resolution_counts.get(instance.instance_id, 0),
        } for instance in dataset.instances]),
        id_column="instance_id",
        data_column="problem_statement",
    )

    # Get entries for the split
    entries = split.get_all_entries()
    
    # Sort by resolve rate and take top N if specified
    if top_n is not None:
        # Get resolve rates for sorting
        resolve_rates = {}
        for entry in entries:
            try:
                system = Evaluation.from_github(split, entry)
                resolve_rates[entry] = len(system.results.resolved) / len(system.predictions)
            except ValueError as e:
                print(f"Skipping {entry} during sorting: {e}")
                continue
        
        # Sort and take top N
        entries = sorted(resolve_rates.keys(), key=lambda e: resolve_rates[e], reverse=True)[:top_n]

    for entry in entries:
        print(f"Processing system {entry}...")
        try:
            system = Evaluation.from_github(split, entry)
        except ValueError as e:
            print(f"Skipping {entry}: {e}")
            continue

        data = pd.DataFrame(
            [
                {
                    "instance_id": prediction.instance_id,
                    "resolved": system.results.is_resolved(prediction.instance_id),
                    "output": {
                        "status": "✅ Success" if system.results.is_resolved(prediction.instance_id)
                                else "❌ Failed" if prediction.patch
                                else "Not attempted",
                        "resolution_count": f"{resolution_counts.get(prediction.instance_id, 0)} systems",
                        "patch": prediction.patch or "No patch generated",
                    }
                }
                for prediction in system.predictions
            ]
        )

        # Some systems have duplicated entries, which Zeno doesn't like.
        if len(data["instance_id"].unique()) != len(data["instance_id"]):
            print(f"{entry} has duplicated entries.")
            data.drop_duplicates("instance_id", inplace=True)

        viz_project.upload_system(
            data,
            name=entry,
            id_column="instance_id",
            output_column="output",
        )


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
