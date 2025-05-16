# Changes

## Trajectory Duration Analysis

Added functionality to calculate and display trajectory durations from timestamp data in the `report.py` script (previously `count_resolved.py`). 

### Changes include:
- Moved `count_resolved.py` to `report/report.py` for better organization
- Added timestamp extraction from trajectory history entries
- Implemented duration calculation and statistics
- Added formatted output for duration metrics in both seconds and minutes

### Key Findings:
- Analysis of trajectory durations shows that unresolved instances typically take 27-35% longer than resolved ones
- In the large dataset (500 instances): Resolved instances averaged 4.11 minutes vs unresolved 5.55 minutes (35% longer)
- In the small dataset (7 instances): Resolved instances averaged 6.70 minutes vs unresolved 8.54 minutes (27% longer)

### Usage:
```bash
python report/report.py <jsonl_file>
```

The script will output detailed statistics including:
- Resolution counts and percentages
- Solution recall, precision, and F-measure metrics
- Cost statistics for all, resolved, and unresolved instances
- Duration statistics for all, resolved, and unresolved instances (in both seconds and minutes)