#!/usr/bin/env python3
"""Cost of Living Comparison Tool.

Fetches living wage data from MIT's Living Wage Calculator and compares
US metro areas, counties, or states across all expense categories.

Data source: https://livingwage.mit.edu
Usage is within their stated 10-location fair-use policy.
"""

import argparse
import json
import math
import os
import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Default database path (relative to this script)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "locations_v1.json")

# Module-level location dicts, populated by load_database()
METROS: dict[str, str] = {}
COUNTIES: dict[str, str] = {}
STATES: dict[str, str] = {}


def load_database(path: str = DEFAULT_DB_PATH) -> None:
    """Load location database from a JSON file into module globals."""
    global METROS, COUNTIES, STATES
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Database file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in database file {path}: {e}", file=sys.stderr)
        sys.exit(1)
    METROS = data.get("metros", {})
    COUNTIES = data.get("counties", {})
    STATES = data.get("states", {})

# Family configuration labels: key -> (display name, column index in tables)
FAMILY_KEYS = [
    "1a0c", "1a1c", "1a2c", "1a3c",
    "2a1w0c", "2a1w1c", "2a1w2c", "2a1w3c",
    "2a2w0c", "2a2w1c", "2a2w2c", "2a2w3c",
]

FAMILY_LABELS = {
    "1a0c": "1 Adult, 0 Children",
    "1a1c": "1 Adult, 1 Child",
    "1a2c": "1 Adult, 2 Children",
    "1a3c": "1 Adult, 3 Children",
    "2a1w0c": "2 Adults (1 Working), 0 Children",
    "2a1w1c": "2 Adults (1 Working), 1 Child",
    "2a1w2c": "2 Adults (1 Working), 2 Children",
    "2a1w3c": "2 Adults (1 Working), 3 Children",
    "2a2w0c": "2 Adults (Both Working), 0 Children",
    "2a2w1c": "2 Adults (Both Working), 1 Child",
    "2a2w2c": "2 Adults (Both Working), 2 Children",
    "2a2w3c": "2 Adults (Both Working), 3 Children",
}

EXPENSE_CATEGORIES = [
    "Food",
    "Child Care",
    "Medical",
    "Housing",
    "Transportation",
    "Civic",
    "Internet & Mobile",
    "Other",
]

# The full list of row labels we look for in the annual expenses table,
# including required income rows.
ANNUAL_ROW_LABELS = EXPENSE_CATEGORIES + [
    "Required annual income before taxes",
    "Annual taxes",
    "Required annual income after taxes",
]


# ---------------------------------------------------------------------------
# Search / lookup helpers
# ---------------------------------------------------------------------------

def search_locations(query: str) -> list[tuple[str, str, str]]:
    """Fuzzy-search metros, counties, and states. Returns list of (type, code, name)."""
    q = query.lower()
    results: list[tuple[str, str, str]] = []

    for code, name in METROS.items():
        if q in name.lower():
            results.append(("metro", code, name))
    for code, name in COUNTIES.items():
        if q in name.lower():
            results.append(("county", code, name))
    for code, name in STATES.items():
        if q in name.lower():
            results.append(("state", code, name))

    return results


def resolve_search_term(term: str) -> tuple[str, str, str]:
    """Resolve a search term to (type, code, name). Exits on ambiguity."""
    matches = search_locations(term)
    if not matches:
        print(f"Error: No location found matching '{term}'.")
        print("Use --list to see available locations, or provide codes directly.")
        sys.exit(1)
    if len(matches) == 1:
        return matches[0]

    # Check which location types matched
    types_found = set(m[0] for m in matches)

    # If only one type matched, apply within-type disambiguation
    if len(types_found) == 1:
        typ = types_found.pop()
        # For a single type with one result, return it
        if len(matches) == 1:
            return matches[0]
        # Prefer match whose name starts with the query
        starting = [m for m in matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # Multiple types matched — if only one metro, prefer it (most common use case)
    metro_matches = [m for m in matches if m[0] == "metro"]
    county_matches = [m for m in matches if m[0] == "county"]
    state_matches = [m for m in matches if m[0] == "state"]

    # If there are both metros and counties (and/or states), always disambiguate
    # so the user can pick the right granularity
    if metro_matches and county_matches:
        _print_disambiguation(term, matches)
        sys.exit(1)

    # Only metros matched (multiple) — try narrowing
    if metro_matches and not county_matches:
        if len(metro_matches) == 1:
            return metro_matches[0]
        starting = [m for m in metro_matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # Only counties matched (multiple) — try narrowing
    if county_matches and not metro_matches:
        if len(county_matches) == 1:
            return county_matches[0]
        starting = [m for m in county_matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # If no metro or county match, prefer exact state name match
    if not metro_matches and not county_matches:
        for m in state_matches:
            if m[2].lower() == term.lower():
                return m

    _print_disambiguation(term, matches)
    sys.exit(1)


def _print_disambiguation(term: str, matches: list[tuple[str, str, str]]) -> None:
    """Print disambiguation list grouped by type."""
    type_order = ["metro", "county", "state"]
    type_labels = {"metro": "Metro Areas", "county": "Counties", "state": "States"}
    type_flags = {"metro": "--metros", "county": "--counties", "state": "--states"}

    print(f"Multiple locations match '{term}':")
    for typ in type_order:
        group = [m for m in matches if m[0] == typ]
        if group:
            print(f"\n  {type_labels[typ]}:")
            flag = type_flags[typ]
            for _, code, name in group:
                print(f"    {flag} {code}  {name}")
    print(f"\nTip: use --metros, --counties, or --states with the codes above.")


def location_url(loc_type: str, code: str) -> str:
    """Build MIT Living Wage Calculator URL."""
    base = "https://livingwage.mit.edu"
    if loc_type == "metro":
        return f"{base}/metros/{code}"
    elif loc_type == "county":
        return f"{base}/counties/{code}"
    elif loc_type == "state":
        return f"{base}/states/{code}"
    else:
        print(f"Error: Unknown location type '{loc_type}'.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Scraping / parsing
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> BeautifulSoup:
    """Fetch a page and return parsed HTML."""
    headers = {
        "User-Agent": (
            "COL-Compare-Tool/1.0 (cost-of-living research; "
            "respects 10-location fair-use policy)"
        ),
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_dollar(text: str) -> Optional[float]:
    """Parse a dollar string like '$1,234' or '$1,234.56' to float."""
    text = text.strip().replace(",", "").replace("$", "").replace("−", "-").replace("–", "-")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_wage(text: str) -> Optional[float]:
    """Parse a wage string like '$28.89' to float."""
    return parse_dollar(text)


def _extract_table_rows(soup: BeautifulSoup, table_id: str) -> list[list[str]]:
    """Extract rows from a table by its id. Returns list of [label, val1, val2, ...]."""
    table = soup.find("table", id=table_id)
    if not table:
        return []
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if cells:
            rows.append([c.get_text(strip=True) for c in cells])
    return rows


def _find_table_by_heading(soup: BeautifulSoup, heading_text: str) -> Optional[BeautifulSoup]:
    """Find a table that follows a heading containing the given text."""
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div"]):
        if heading_text.lower() in heading.get_text(strip=True).lower():
            table = heading.find_next("table")
            if table:
                return table
    return None


def _parse_table_to_rows(table) -> list[list[str]]:
    """Parse a BeautifulSoup table element into a list of text rows."""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if cells:
            rows.append([c.get_text(strip=True) for c in cells])
    return rows


def _match_row_label(row_label: str, target: str) -> bool:
    """Check if a row label matches a target category, with fuzzy matching."""
    rl = row_label.lower().strip()
    tl = target.lower().strip()
    # Direct containment
    if tl in rl or rl in tl:
        return True
    # Handle some known variations
    aliases = {
        "internet & mobile": ["broadband", "internet", "telephone"],
        "civic": ["civic"],
        "other": ["other necessities", "other"],
        "food": ["food"],
        "child care": ["child care", "childcare"],
        "medical": ["medical"],
        "housing": ["housing"],
        "transportation": ["transportation"],
        "required annual income before taxes": [
            "required annual income before taxes",
            "annual income before taxes",
            "income before taxes",
        ],
        "annual taxes": ["annual taxes", "taxes"],
        "required annual income after taxes": [
            "required annual income after taxes",
            "annual income after taxes",
            "income after taxes",
        ],
    }
    for key, als in aliases.items():
        if tl == key:
            return any(a in rl for a in als)
    return False


def parse_location_data(soup: BeautifulSoup) -> dict:
    """Parse all relevant data from a Living Wage Calculator page.

    Returns dict with:
        name: str - location name
        wages: dict[family_key -> float] - hourly living wage
        expenses: dict[category -> dict[family_key -> float]] - annual expenses
        income_before_tax: dict[family_key -> float]
        income_after_tax: dict[family_key -> float]
        taxes: dict[family_key -> float]
    """
    data: dict = {}

    # Extract location name from heading or title
    # The h1 is the site logo; the location is in an h2 like
    # "Living Wage Calculation for Atlanta-Sandy Springs-Alpharetta, GA"
    name = "Unknown"
    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(strip=True)
        for prefix in [
            "Living Wage Calculation for ",
            "Living Wage Calculator for ",
        ]:
            if text.startswith(prefix):
                name = text[len(prefix):]
                break
        if name != "Unknown":
            break

    if name == "Unknown":
        title = soup.find("title")
        if title:
            t = title.get_text(strip=True)
            m = re.search(r"for\s+(.+)$", t)
            if m:
                name = m.group(1).strip()

    data["name"] = name

    # --- Parse hourly living wage table ---
    # Look for table with "Living Wage" as header
    wage_table = None
    for table in soup.find_all("table"):
        text = table.get_text(strip=True).lower()
        if "living wage" in text and ("poverty wage" in text or "minimum wage" in text):
            wage_table = table
            break

    wages = {}
    if wage_table:
        rows = _parse_table_to_rows(wage_table)
        for row in rows:
            if row and "living wage" in row[0].lower():
                values = row[1:]  # skip label
                for i, key in enumerate(FAMILY_KEYS):
                    if i < len(values):
                        w = parse_wage(values[i])
                        if w is not None:
                            wages[key] = w
                break
    data["wages"] = wages

    # --- Parse annual expenses table ---
    # Look for the "Typical Expenses" table
    expense_table = None
    for table in soup.find_all("table"):
        table_text = table.get_text(strip=True).lower()
        if "typical expenses" in table_text or (
            "food" in table_text and "housing" in table_text and "transportation" in table_text
        ):
            # Check it has dollar amounts (to distinguish from the wage table)
            first_data_row = None
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if cells and len(cells) > 1:
                    first_data_row = cells
                    break
            if first_data_row and "$" in first_data_row[0].get_text():
                # This is likely the right table, but the label is in the first column
                pass
            if first_data_row:
                expense_table = table
                break

    expenses: dict[str, dict[str, float]] = {}
    income_before_tax: dict[str, float] = {}
    income_after_tax: dict[str, float] = {}
    taxes: dict[str, float] = {}

    if expense_table:
        rows = _parse_table_to_rows(expense_table)
        for row in rows:
            if not row or len(row) < 2:
                continue
            label = row[0]
            values = row[1:]

            # Check each known category
            for cat in EXPENSE_CATEGORIES:
                if _match_row_label(label, cat):
                    expenses[cat] = {}
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                expenses[cat][key] = v
                    break
            else:
                # Check income/tax rows
                if _match_row_label(label, "Required annual income before taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                income_before_tax[key] = v
                elif _match_row_label(label, "Annual taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                taxes[key] = v
                elif _match_row_label(label, "Required annual income after taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                income_after_tax[key] = v

    data["expenses"] = expenses
    data["income_before_tax"] = income_before_tax
    data["income_after_tax"] = income_after_tax
    data["taxes"] = taxes

    return data


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def _adjust_living_wage(
    lw: float, loc: Optional[dict], family: str, excluded: set[str]
) -> float:
    """Subtract excluded expense categories from a living-wage total."""
    if not excluded or loc is None:
        return lw
    for cat in excluded:
        lw -= loc.get("expenses", {}).get(cat, {}).get(family, 0.0)
    return lw


def compute_equivalent_income(
    income_a: float,
    lw_before_tax_a: float,
    lw_before_tax_b: float,
    method: str = "sqrt",
    loc_a: Optional[dict] = None,
    loc_b: Optional[dict] = None,
    family: str = "1a0c",
    excluded: Optional[set[str]] = None,
) -> float:
    """Compute equivalent income in location B for someone earning income_a in A.

    Methods:
        linear     — Simple ratio: income * (lw_b / lw_a)
        sqrt       — Living-wage portion scales fully, excess dampened by sqrt
        log-linear — Constant elasticity: income * ratio^0.75
        engel      — Non-homothetic Engel curve using per-category expense data

    When categories are excluded, their expenses are subtracted from the
    living-wage anchors so the ratio reflects only the included categories.
    """
    excluded = excluded or set()

    # Adjust living-wage anchors by removing excluded category expenses
    adj_a = _adjust_living_wage(lw_before_tax_a, loc_a, family, excluded)
    adj_b = _adjust_living_wage(lw_before_tax_b, loc_b, family, excluded)

    if adj_a <= 0 or adj_b <= 0:
        return income_a

    ratio = adj_b / adj_a

    if method == "linear":
        return income_a * ratio

    elif method == "sqrt":
        if income_a <= adj_a:
            return income_a * ratio
        else:
            base = adj_b
            excess = (income_a - adj_a) * math.sqrt(ratio)
            return base + excess

    elif method == "log-linear":
        elasticity = 0.75
        return income_a * (ratio ** elasticity)

    elif method == "engel":
        if loc_a is None or loc_b is None:
            # Fall back to sqrt if expense data unavailable
            return compute_equivalent_income(
                income_a, lw_before_tax_a, lw_before_tax_b,
                method="sqrt", excluded=excluded,
            )

        # Compute housing and non-housing expense totals for each location
        housing_excluded = "Housing" in excluded
        housing_a = (
            0.0 if housing_excluded
            else loc_a.get("expenses", {}).get("Housing", {}).get(family, 0.0)
        )
        housing_b = (
            0.0 if housing_excluded
            else loc_b.get("expenses", {}).get("Housing", {}).get(family, 0.0)
        )

        non_housing_a = 0.0
        non_housing_b = 0.0
        for cat in EXPENSE_CATEGORIES:
            if cat == "Housing" or cat in excluded:
                continue
            non_housing_a += loc_a.get("expenses", {}).get(cat, {}).get(family, 0.0)
            non_housing_b += loc_b.get("expenses", {}).get(cat, {}).get(family, 0.0)

        # Compute per-category ratios (guard against zero)
        housing_ratio = (housing_b / housing_a) if housing_a > 0 else ratio
        non_housing_ratio = (
            (non_housing_b / non_housing_a) if non_housing_a > 0 else ratio
        )

        # Housing share at the living wage level
        total_expenses_a = housing_a + non_housing_a
        housing_share_at_lw = (
            (housing_a / total_expenses_a) if total_expenses_a > 0 else 0.3
        )

        # Engel curve: housing share decreases with income
        if adj_a > 0 and income_a > 0:
            housing_share = housing_share_at_lw * (
                (adj_a / income_a) ** 0.3
            )
        else:
            housing_share = housing_share_at_lw

        effective_ratio = (
            housing_share * housing_ratio
            + (1 - housing_share) * non_housing_ratio
        )
        return income_a * effective_ratio

    else:
        # Unknown method, fall back to sqrt
        return compute_equivalent_income(
            income_a, lw_before_tax_a, lw_before_tax_b,
            method="sqrt", excluded=excluded,
        )


def format_dollar(val: float) -> str:
    """Format a float as a dollar string."""
    if val < 0:
        return f"-${abs(val):,.0f}"
    return f"${val:,.0f}"


def format_pct(val: float) -> str:
    """Format a percentage change."""
    if val > 0:
        return f"+{val:.1f}%"
    return f"{val:.1f}%"


def pct_diff(a: float, b: float) -> Optional[float]:
    """Percentage difference of b relative to a."""
    if a == 0:
        return None
    return ((b - a) / a) * 100


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

METHOD_LABELS = {
    "linear": "Linear Ratio",
    "sqrt": "Blended Square Root",
    "log-linear": "Constant Elasticity (e=0.75)",
    "engel": "Engel Curve (Non-Homothetic)",
}


def print_comparison(
    locations: list[dict],
    family: str,
    income: Optional[float] = None,
    method: str = "sqrt",
    excluded: Optional[set[str]] = None,
) -> None:
    """Print a formatted comparison table."""
    excluded = excluded or set()
    active_categories = [c for c in EXPENSE_CATEGORIES if c not in excluded]

    family_label = FAMILY_LABELS.get(family, family)
    names = [loc["name"] for loc in locations]

    print()
    print("Cost of Living Comparison")
    print("=" * 60)
    print("  vs  ".join(names))
    print(f"Family type: {family_label}")
    if excluded:
        print(f"Excluded:    {', '.join(sorted(excluded))}")
    print()

    # --- Headline income equivalence ---
    if income is not None and len(locations) >= 2:
        ref = locations[0]
        ref_bt = ref["income_before_tax"].get(family)
        if ref_bt:
            method_label = METHOD_LABELS.get(method, method)
            print(f"INCOME EQUIVALENCE  [method: {method_label}]")
            print("-" * 60)
            for loc in locations[1:]:
                loc_bt = loc["income_before_tax"].get(family)
                if loc_bt:
                    equiv = compute_equivalent_income(
                        income, ref_bt, loc_bt,
                        method=method,
                        loc_a=ref,
                        loc_b=loc,
                        family=family,
                        excluded=excluded,
                    )
                    diff_pct = pct_diff(income, equiv)
                    direction = "less" if diff_pct and diff_pct < 0 else "more"
                    pct_str = f" ({abs(diff_pct):.1f}% {direction})" if diff_pct else ""
                    print(
                        f"  {format_dollar(income)} in {ref['name']}"
                        f"  ~  {format_dollar(equiv)} in {loc['name']}{pct_str}"
                    )
            print()

    # --- Expense breakdown ---
    # Column widths
    cat_width = 20
    val_width = max(14, max(len(n) for n in names) + 2)

    # Header
    header = f"{'Category':<{cat_width}}"
    for name in names:
        header += f"{name:>{val_width}}"
    if len(locations) >= 2:
        header += f"{'Diff':>10}"
    print("Expense Breakdown (Annual):")
    print(header)
    print("\u2500" * len(header))

    total_by_loc: list[float] = [0.0] * len(locations)

    for cat in active_categories:
        row = f"{cat:<{cat_width}}"
        vals: list[Optional[float]] = []
        for loc in locations:
            v = loc["expenses"].get(cat, {}).get(family)
            vals.append(v)
        for i, v in enumerate(vals):
            if v is not None:
                row += f"{format_dollar(v):>{val_width}}"
                total_by_loc[i] += v
            else:
                row += f"{'N/A':>{val_width}}"
        if len(locations) >= 2 and vals[0] is not None and vals[1] is not None:
            pd = pct_diff(vals[0], vals[1])
            row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
        print(row)

    # Taxes row
    row = f"{'Taxes':<{cat_width}}"
    tax_vals: list[Optional[float]] = []
    for loc in locations:
        v = loc["taxes"].get(family)
        tax_vals.append(v)
    for i, v in enumerate(tax_vals):
        if v is not None:
            row += f"{format_dollar(v):>{val_width}}"
            total_by_loc[i] += v
        else:
            row += f"{'N/A':>{val_width}}"
    if len(locations) >= 2 and tax_vals[0] is not None and tax_vals[1] is not None:
        pd = pct_diff(tax_vals[0], tax_vals[1])
        row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
    print(row)

    print("\u2500" * len(header))

    # Total before tax row
    row = f"{'Total (pre-tax)':<{cat_width}}"
    bt_vals: list[Optional[float]] = []
    for loc in locations:
        v = loc["income_before_tax"].get(family)
        bt_vals.append(v)
    for i, v in enumerate(bt_vals):
        if v is not None:
            row += f"{format_dollar(v):>{val_width}}"
        else:
            row += f"{'N/A':>{val_width}}"
    if len(locations) >= 2 and bt_vals[0] is not None and bt_vals[1] is not None:
        pd = pct_diff(bt_vals[0], bt_vals[1])
        row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
    print(row)

    print()

    # Living wage
    row = f"{'Living Wage':<{cat_width}}"
    for loc in locations:
        w = loc["wages"].get(family)
        if w is not None:
            row += f"{'${:.2f}/hr'.format(w):>{val_width}}"
        else:
            row += f"{'N/A':>{val_width}}"
    print(row)

    print()
    print("Data source: MIT Living Wage Calculator (https://livingwage.mit.edu)")
    print()


def print_single_location(
    loc: dict,
    family: str,
    excluded: Optional[set[str]] = None,
) -> None:
    """Print data for a single location."""
    excluded = excluded or set()
    active_categories = [c for c in EXPENSE_CATEGORIES if c not in excluded]

    family_label = FAMILY_LABELS.get(family, family)
    print()
    print(f"Living Wage Data: {loc['name']}")
    print("=" * 50)
    print(f"Family type: {family_label}")
    if excluded:
        print(f"Excluded:    {', '.join(sorted(excluded))}")
    print()

    wage = loc["wages"].get(family)
    if wage is not None:
        print(f"  Living Wage: ${wage:.2f}/hr")

    bt = loc["income_before_tax"].get(family)
    if bt is not None:
        print(f"  Required Annual Income (before tax): {format_dollar(bt)}")

    at = loc["income_after_tax"].get(family)
    if at is not None:
        print(f"  Required Annual Income (after tax):  {format_dollar(at)}")

    print()
    print("  Annual Expenses:")
    for cat in active_categories:
        v = loc["expenses"].get(cat, {}).get(family)
        if v is not None:
            print(f"    {cat:<22} {format_dollar(v)}")

    tax = loc["taxes"].get(family)
    if tax is not None:
        print(f"    {'Taxes':<22} {format_dollar(tax)}")

    print()
    print("Data source: MIT Living Wage Calculator (https://livingwage.mit.edu)")
    print()


def list_locations() -> None:
    """Print all known locations."""
    print("\nMetro Areas (use with --metros <code>):")
    print("-" * 60)
    for code, name in sorted(METROS.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")

    print(f"\nCounties (use with --counties <code>):")
    print("-" * 60)
    for code, name in sorted(COUNTIES.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")

    print(f"\nStates (use with --states <code>):")
    print("-" * 60)
    for code, name in sorted(STATES.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")
    print()
    print("Any county or metro can also be used by FIPS/CBSA code directly,")
    print("even if not listed above. Find codes at https://livingwage.mit.edu")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare cost of living between US locations using MIT Living Wage data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --search "New York" "Atlanta"
  %(prog)s --search "New York" "Atlanta" --income 120000
  %(prog)s --search "San Francisco" "Austin" --family 2a2w1c
  %(prog)s --metros 35620 12060
  %(prog)s --counties 06075 06037
  %(prog)s --states 06 48
  %(prog)s --list
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--search", nargs="+", metavar="TERM",
        help="Search for locations by name (e.g., 'New York' 'Atlanta')",
    )
    group.add_argument(
        "--metros", nargs="+", metavar="CBSA",
        help="Metro areas by CBSA code (e.g., 35620 12060)",
    )
    group.add_argument(
        "--counties", nargs="+", metavar="FIPS",
        help="Counties by FIPS code (e.g., 06075 06037)",
    )
    group.add_argument(
        "--states", nargs="+", metavar="FIPS",
        help="States by FIPS code (e.g., 06 48)",
    )
    group.add_argument(
        "--list", action="store_true",
        help="List all known metro areas and states",
    )

    parser.add_argument(
        "--family", default="1a0c",
        choices=FAMILY_KEYS,
        help="Family configuration (default: 1a0c = 1 Adult, 0 Children)",
    )
    parser.add_argument(
        "--income", type=float, default=None,
        help="Annual income in first location for equivalence calculation",
    )
    parser.add_argument(
        "--method", default="sqrt",
        choices=["linear", "sqrt", "log-linear", "engel"],
        help=(
            "Income equivalence method: "
            "linear (simple ratio), "
            "sqrt (blended square root, default), "
            "log-linear (constant elasticity e=0.75), "
            "engel (non-homothetic Engel curve)"
        ),
    )
    parser.add_argument(

        "--exclude", nargs="+", metavar="CATEGORY",
        help=(
            "Exclude one or more expense categories from the comparison. "
            "Available categories: "
            + ", ".join(EXPENSE_CATEGORIES)
        ))

    parser.add_argument (
        "--database", default=DEFAULT_DB_PATH, metavar="PATH",
        help="Path to location database JSON file (default: database/locations_v1.json)",
    )

    return parser


def resolve_excluded_categories(raw: list[str]) -> set[str]:
    """Resolve user-provided category names to canonical EXPENSE_CATEGORIES names.

    Matching is case-insensitive. Exits with an error for unrecognized names.
    """
    lookup = {cat.lower(): cat for cat in EXPENSE_CATEGORIES}
    resolved: set[str] = set()
    for name in raw:
        canon = lookup.get(name.lower())
        if canon is None:
            print(f"Error: Unknown expense category '{name}'.")
            print(f"Available categories: {', '.join(EXPENSE_CATEGORIES)}")
            sys.exit(1)
        resolved.add(canon)
    return resolved


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    load_database(args.database)

    if args.list:
        list_locations()
        return

    # Resolve locations
    loc_specs: list[tuple[str, str]] = []  # (type, code)

    if args.search:
        for term in args.search:
            typ, code, name = resolve_search_term(term)
            loc_specs.append((typ, code))
    elif args.metros:
        for code in args.metros:
            loc_specs.append(("metro", code))
    elif args.counties:
        for code in args.counties:
            loc_specs.append(("county", code))
    elif args.states:
        for code in args.states:
            loc_specs.append(("state", code))
    else:
        parser.print_help()
        return

    if not loc_specs:
        print("Error: No locations specified.")
        sys.exit(1)

    # Fetch data for each location
    location_data: list[dict] = []
    for loc_type, code in loc_specs:
        url = location_url(loc_type, code)
        print(f"Fetching data from {url} ...", file=sys.stderr)
        try:
            soup = fetch_page(url)
            data = parse_location_data(soup)
            data["url"] = url
            location_data.append(data)
        except requests.HTTPError as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
            sys.exit(1)
        except requests.ConnectionError as e:
            print(f"Connection error for {url}: {e}", file=sys.stderr)
            sys.exit(1)

    # Display
    family = args.family
    excluded = resolve_excluded_categories(args.exclude) if args.exclude else set()
    if len(location_data) == 1:
        print_single_location(location_data[0], family, excluded=excluded)
    else:
        print_comparison(location_data, family, income=args.income, method=args.method, excluded=excluded)


if __name__ == "__main__":
    main()
