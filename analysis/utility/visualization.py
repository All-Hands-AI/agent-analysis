import pandas as pd


def set_column_awards(df: pd.DataFrame, column: str, descending: bool = True) -> None:
    """Set awards for the top 3 values in a DataFrame column.

    Args:
        df: DataFrame containing the column to award.
        column: Name of the column to award.
        descending: Whether to award the top 3 values (True) or the bottom 3 values (False).
    """
    top_values = df[column].nlargest(3) if descending else df[column].nsmallest(3)

    for rank, (idx, _) in enumerate(top_values.items(), 1):
        if rank == 1:
            df.loc[idx, column] = f"🥇 {df.loc[idx, column]:.2f}"
        elif rank == 2:
            df.loc[idx, column] = f"🥈 {df.loc[idx, column]:.2f}"
        elif rank == 3:
            df.loc[idx, column] = f"🥉 {df.loc[idx, column]:.2f}"
