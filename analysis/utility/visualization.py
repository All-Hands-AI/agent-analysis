import pandas as pd

def set_column_awards(df: pd.DataFrame, column: str, descending: bool = True) -> None:
    """Set awards for the top 3 values in a DataFrame column.

    Args:
        df: DataFrame containing the column to award.
        column: Name of the column to award.
        descending: Whether to award the top 3 values (True) or the bottom 3 values (False).
    """
    # Grab the original column dtype and the top 3 values

    col = pd.Series(df[column])
    col_dtype = col.dtype
    top_3_values = list(sorted(col.unique(), reverse=descending))[:3]

    def format_entry(value: col_dtype) -> str:
        """Format an entry in the column."""
        # Format value based on dtype
        if isinstance(value, float):
            formatted_value = f"{value:.2f}"
        else:
            formatted_value = str(value)

        award = ""
        for medal, medaled_value in zip(["🥇", "🥈", "🥉"], top_3_values):
            if value == medaled_value:
                award = medal + " "
                break

        return award + formatted_value

    df[column] = df[column].apply(format_entry)
