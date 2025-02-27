import pandas as pd
from scipy.stats import kruskal
from pydantic import BaseModel, Field


class Group(BaseModel):
    name: str | int | bool = Field(
        description="The name of the group (the value of the target)"
    )
    size: int = Field(description="The number of samples in the group")


class Relevance(BaseModel):
    statistic: float = Field(description="The Kruskal-Wallis H statistic")
    p_value: float = Field(description="The p-value of the Kruskal-Wallis test")
    groups: list[Group] = Field(description="The groups used in the test")
    feature: str = Field(description="The name of the feature being tested")
    target: str = Field(
        description="The name of the target variable inducing the groups"
    )

    @property
    def effect_size(self) -> float:
        """
        Compute the effect size of the Kruskal-Wallis test using the epsilon-squared measure.
        """
        total_samples = sum(group.size for group in self.groups)
        return self.statistic / (total_samples**2 - 1)


def feature_relevance(df: pd.DataFrame, feature: str, target: str) -> Relevance:
    """
    Compute the relevance of a feature to a target using a Kruskal-Wallis test.

    Args:
        df: Dataframe holding the data -- must have the feature and target as columns
    
        feature: The name of the feature to test

        target: The name of the target variable, should be categorical (str | int | bool)

    Raises:
        ValueError: if the groups cannot be separated by the Kruskal-Wallis test
    """
    # Find all unique values in the target -- these will be our groups
    groups = []
    data = []
    for label in df[target].unique():
        group_data = df[df[target] == label][feature]
        data.append(group_data.dropna())
        groups.append(Group(name=label, size=len(group_data)))

    # Run the Kruskal-Wallis test
    statistic, p_value = kruskal(*data)

    return Relevance(
        statistic=statistic,
        p_value=p_value,
        groups=groups,
        feature=feature,
        target=target,
    )
