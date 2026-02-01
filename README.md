# col-compare

A command-line tool that compares cost of living between US locations using data from [MIT's Living Wage Calculator](https://livingwage.mit.edu).

Given two or more locations, it fetches living wage data, breaks down annual expenses by category, and calculates what a given income in one city is equivalent to in another.

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Usage

### Search by location name

```bash
python col_compare.py --search "New York" "Atlanta"
```

### Compare with income equivalence

```bash
python col_compare.py --search "San Francisco" "Austin" --income 150000
```

This shows what a $150,000 salary in San Francisco is equivalent to in Austin, using a blended scaling model where the living-wage portion scales by the full cost-of-living ratio and excess income scales by the square root of that ratio.

### Specify a family configuration

```bash
python col_compare.py --search "Boston" "Denver" --family 2a2w1c
```

Available family configurations:

| Key | Description |
|---|---|
| `1a0c` | 1 Adult, 0 Children (default) |
| `1a1c` | 1 Adult, 1 Child |
| `1a2c` | 1 Adult, 2 Children |
| `1a3c` | 1 Adult, 3 Children |
| `2a1w0c` | 2 Adults (1 Working), 0 Children |
| `2a1w1c` | 2 Adults (1 Working), 1 Child |
| `2a1w2c` | 2 Adults (1 Working), 2 Children |
| `2a1w3c` | 2 Adults (1 Working), 3 Children |
| `2a2w0c` | 2 Adults (Both Working), 0 Children |
| `2a2w1c` | 2 Adults (Both Working), 1 Child |
| `2a2w2c` | 2 Adults (Both Working), 2 Children |
| `2a2w3c` | 2 Adults (Both Working), 3 Children |

### Use location codes directly

```bash
# Metro areas by CBSA code
python col_compare.py --metros 35620 12060

# Counties by FIPS code
python col_compare.py --counties 06075 06037

# States by FIPS code
python col_compare.py --states 06 48
```

### List all available locations

```bash
python col_compare.py --list
```

## What it reports

For each comparison, the tool displays:

- **Income equivalence** -- what your salary in one city buys you in another
- **Hourly living wage** for the selected family type
- **Annual expenses** broken down by category: Food, Child Care, Medical, Housing, Transportation, Civic, Internet & Mobile, Other
- **Required annual income** before and after taxes
- **Percentage differences** between locations for each category

## How income equivalence works

The tool uses a blended approach rather than a simple ratio:

1. The portion of income up to the living wage scales by the full cost-of-living ratio between locations.
2. Income above the living wage scales by the *square root* of that ratio, reflecting the fact that discretionary spending differences are dampened compared to baseline cost differences.

This produces more realistic estimates than a flat multiplier.

## Data source

All data is fetched live from [MIT's Living Wage Calculator](https://livingwage.mit.edu). The tool covers ~410 metro areas, ~80 counties, and all 50 US states plus DC. Usage stays within MIT's stated 10-location fair-use policy.

## License

MIT
