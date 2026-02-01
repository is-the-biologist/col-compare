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

This shows what a $150,000 salary in San Francisco is equivalent to in Austin. By default it uses the blended square-root method (see below).

### Choose an income equivalence method

```bash
python col_compare.py --search "New York" "Atlanta" --income 150000 --method engel
```

Available methods: `linear`, `sqrt` (default), `log-linear`, `engel`. See [Income equivalence methods](#income-equivalence-methods) for details.

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

## Income equivalence methods

The `--method` flag controls how income is translated between locations. All methods use the required annual income before taxes from MIT's data as the cost-of-living anchor.

### `linear` — Simple Ratio

```
equiv = income × (lw_b / lw_a)
```

Treats all income as equally location-sensitive. This is the approach used by most consumer COL calculators (CNN Money, BankRate, NerdWallet). Simple but tends to overstate differences at high incomes.

**Source:** C2ER COLI methodology.

### `sqrt` — Blended Square Root (default)

```
base  = lw_b
excess = (income − lw_a) × √(lw_b / lw_a)
equiv  = base + excess
```

The living-wage portion scales by the full COL ratio; income above the living wage scales by the square root of that ratio. This dampens the adjustment for higher earners whose marginal spending is less location-sensitive.

### `log-linear` — Constant Elasticity

```
equiv = income × ratio^0.75    where ratio = lw_b / lw_a
```

Inspired by Mincerian log-linear wage equations. An elasticity of 0.75 means a 10% COL difference produces a ~7.5% income adjustment, capturing the empirical finding that wages don't fully compensate for COL differences.

**Source:** Mincer (1974); BLS research on RPP-adjusted wages.

### `engel` — Non-Homothetic / Engel Curve

```
housing_share(income) = housing_share_at_lw × (lw_a / income)^0.3
effective_ratio = housing_share × housing_ratio + (1 − housing_share) × non_housing_ratio
equiv = income × effective_ratio
```

Uses the actual per-category expense data to compute separate housing and non-housing cost ratios. Housing's share of the budget decreases with income (Engel's law applied to housing), so higher earners get a smaller COL adjustment since housing is typically the biggest driver of geographic price differences.

**Source:** NBER WP 22816; ERI income-level-dependent differentials.

## Data source

All data is fetched live from [MIT's Living Wage Calculator](https://livingwage.mit.edu). The tool covers ~410 metro areas, ~80 counties, and all 50 US states plus DC. Usage stays within MIT's stated 10-location fair-use policy.

## License

MIT
