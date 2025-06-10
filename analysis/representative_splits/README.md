# Representative Splits

This directory contains tools for creating representative splits of instances based on their resolution counts.

## How to Use split.py

`split.py` is a tool that processes trajectory files and creates representative splits of instance IDs based on their resolution counts.

### Usage

```bash
python split.py --trajectories PATH_TO_TRAJECTORIES [PATH_TO_TRAJECTORIES ...] --split OUTPUT_PATH [--split-size SPLIT_SIZE]
```

### Parameters

- `--trajectories`: One or more paths to trajectory directories or JSONL files. If a directory is provided, the script will look for an `output.jsonl` file within it.
- `--split`: Output path for the TOML file containing instance IDs grouped by resolution counts.
- `--split-size`: (Optional) Size of each representative split. Default is 50.

### Input

The script processes JSONL files containing trajectory data. Each line in the JSONL file should be a valid JSON object with:
- An `instance_id` field or an `instance` object containing an `instance_id` field
- A `report` object with a `resolved` field indicating whether the instance was resolved

### Output

The script generates a TOML file at the specified output path containing:
- Distribution information about resolution counts
- Lists of instance IDs grouped by resolution count
- Representative splits that maintain the same distribution of resolution counts

### Example

```bash
python split.py --trajectories /path/to/trajectories1 /path/to/trajectories2 --split output_splits.toml --split-size 100
```

This will process the trajectory files in the specified directories, count resolved instances, and create representative splits of size 100, saving the results to `output_splits.toml`.