"""
Pydantic models for ClubElo CSV data and win probability calculations.
"""

from pydantic import BaseModel, Field, field_validator


class ClubEloMatch(BaseModel):
    """
    Represents a single match row from ClubElo's CSV.

    The CSV columns include:
    - Date (YYYY-MM-DD)
    - Home (team name)
    - Away (team name)
    - GD=1, GD=2, GD=3, GD=4, GD=5, GD>5 (probabilities for home win by goal difference)
    - GD=-1, GD=-2, GD=-3, GD=-4, GD=-5, GD<-5 (probabilities for away win by goal difference)
    """

    Date: str = Field(description="Match date in YYYY-MM-DD format")
    Home: str = Field(description="Home team name")
    Away: str = Field(description="Away team name")
    GD_1: float = Field(
        alias="GD=1", description="Probability of home win by exactly 1 goal"
    )
    GD_2: float = Field(
        alias="GD=2", description="Probability of home win by exactly 2 goals"
    )
    GD_3: float = Field(
        alias="GD=3", description="Probability of home win by exactly 3 goals"
    )
    GD_4: float = Field(
        alias="GD=4", description="Probability of home win by exactly 4 goals"
    )
    GD_5: float = Field(
        alias="GD=5", description="Probability of home win by exactly 5 goals"
    )
    GD_gt5: float = Field(
        alias="GD>5", description="Probability of home win by more than 5 goals"
    )
    GD_m1: float = Field(
        alias="GD=-1", description="Probability of away win by exactly 1 goal"
    )
    GD_m2: float = Field(
        alias="GD=-2", description="Probability of away win by exactly 2 goals"
    )
    GD_m3: float = Field(
        alias="GD=-3", description="Probability of away win by exactly 3 goals"
    )
    GD_m4: float = Field(
        alias="GD=-4", description="Probability of away win by exactly 4 goals"
    )
    GD_m5: float = Field(
        alias="GD=-5", description="Probability of away win by exactly 5 goals"
    )
    GD_ltm5: float = Field(
        alias="GD<-5", description="Probability of away win by more than 5 goals"
    )

    @field_validator(
        "GD_1",
        "GD_2",
        "GD_3",
        "GD_4",
        "GD_5",
        "GD_gt5",
        "GD_m1",
        "GD_m2",
        "GD_m3",
        "GD_m4",
        "GD_m5",
        "GD_ltm5",
        mode="before",
    )
    @classmethod
    def parse_float(cls, v):
        """Convert string to float, handling empty strings."""
        if isinstance(v, str):
            if v.strip() == "":
                return 0.0
            try:
                return float(v)
            except ValueError:
                return 0.0
        return v

    @property
    def home_win_probability(self) -> float:
        """Total probability of home win (sum of positive GD columns)."""
        return self.GD_1 + self.GD_2 + self.GD_3 + self.GD_4 + self.GD_5 + self.GD_gt5

    @property
    def away_win_probability(self) -> float:
        """Total probability of away win (sum of negative GD columns)."""
        return (
            self.GD_m1
            + self.GD_m2
            + self.GD_m3
            + self.GD_m4
            + self.GD_m5
            + self.GD_ltm5
        )

    def barcelona_win_probability(self) -> float | None:
        """
        Return Barcelona's win probability for this match.

        Returns:
            float if Barcelona is home or away, else None.
        """
        if self.Home == "Barcelona":
            return self.home_win_probability
        if self.Away == "Barcelona":
            return self.away_win_probability
        return None
