# Condenser Notebooks

These notebooks contain common analyses and graphs used to determine the efficacy of condensers in the OpenHands agent infrastructure.

## How to use

Make sure the `analysis` module is installed in the Python environment used by your notebooks.

Each notebook has an empty `filepaths: list[Path] = []` in the first cell. Replace this list with paths referencing folders produced by the OpenHands evaluation infrastructure.

These folders are usually structured as follows:

```
path/to/evaluation/folder/
├─ infer_logs/
|  ├─ instance_astropy__astropy_14309.log
|  ├─ ...
├─ llm_completions/
|  ├─ astropy__astropy_14309/
|  |  ├─ claude-3-7-sonnet-20250219-1746126247.053365.json
|  |  ├─ claude-3-7-sonnet-20250219-1746126249.995289.json
|  |  ├─ ...
|  ├─ ...
├─ logs/
├─ output.jsonl
├─ metadata.json
├─ output.swebench_eval.jsonl
├─ ...
```

These notebooks have only been tested with SWE-bench evaluation results. Other evaluation scripts should produce similar information, but possibly in a different (unsupported) format.