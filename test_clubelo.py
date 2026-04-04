import requests
import csv
from io import StringIO

url = "http://api.clubelo.com/Fixtures"
response = requests.get(url, timeout=10)
csv_reader = csv.DictReader(StringIO(response.text))

# Get first row to see column names
first_row = next(csv_reader)
print("Column names in CSV:")
for i, col in enumerate(first_row.keys()):
    print(f"{i}: {col}")

print("\nChecking for Barcelona matches...")
csv_reader = csv.DictReader(StringIO(response.text))
barca_count = 0
for row in csv_reader:
    home = row.get("Home", "")
    away = row.get("Away", "")
    if home == "Barcelona" or away == "Barcelona":
        barca_count += 1
        date = row.get("Date", "")
        print(f"\nBarcelona match found: {home} vs {away} on {date}")

        # Check if the columns the code expects exist
        expected_cols_home = ["GD=1", "GD=2", "GD=3", "GD=4", "GD=5", "GD>5"]
        expected_cols_away = ["GD=-1", "GD=-2", "GD=-3", "GD=-4", "GD=-5", "GD<-5"]

        missing_home = [col for col in expected_cols_home if col not in row]
        missing_away = [col for col in expected_cols_away if col not in row]

        if missing_home:
            print(f"  Missing home columns: {missing_home}")
        if missing_away:
            print(f"  Missing away columns: {missing_away}")

        # Try to calculate as the code does
        try:
            prob_home_win = sum(
                float(row[col]) for col in expected_cols_home if col in row
            )
            prob_away_win = sum(
                float(row[col]) for col in expected_cols_away if col in row
            )

            if home == "Barcelona":
                prob_barca = prob_home_win
            else:
                prob_barca = prob_away_win

            print(f"  Calculated probability: {prob_barca * 100:.1f}%")
        except Exception as e:
            print(f"  Error calculating: {e}")

print(f"\nTotal Barcelona matches found: {barca_count}")
