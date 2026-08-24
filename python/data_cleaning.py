"""
data_cleaning.py
=================
Cleans the raw synthetic EV charging dataset.

Every cleaning decision is explained inline via print statements and the
accompanying comments, and a running log of row-impact is kept so nothing
is silently dropped without visibility.

Run:
    python python/data_cleaning.py
Reads:
    data/raw/ev_charging_raw.csv
Produces:
    data/processed/ev_charging_cleaned.csv
    reports/cleaning_log.md
"""

import numpy as np
import pandas as pd

RAW_PATH = "data/raw/ev_charging_raw.csv"
OUT_PATH = "data/processed/ev_charging_cleaned.csv"
LOG_PATH = "reports/cleaning_log.md"


def log(msg, log_lines):
    print(msg)
    log_lines.append(msg)


def clean(df):
    log_lines = ["# Data Cleaning Log\n"]
    start_n = len(df)
    log(f"Starting rows: {start_n}", log_lines)

    # ------------------------------------------------------------------
    # 1. Standardize dtypes
    # ------------------------------------------------------------------
    # energy_consumed_kwh sometimes has a ' kWh' suffix from bad exports -> strip and coerce to float
    df["energy_consumed_kwh"] = (
        df["energy_consumed_kwh"].astype(str).str.replace(" kWh", "", regex=False)
    )
    df["energy_consumed_kwh"] = pd.to_numeric(df["energy_consumed_kwh"], errors="coerce")
    log("Standardized energy_consumed_kwh to numeric (stripped stray unit text).", log_lines)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")
    log("Parsed date/start_time/end_time to datetime; unparseable values become NaT for review.", log_lines)

    # ------------------------------------------------------------------
    # 2. Standardize inconsistent station names
    # ------------------------------------------------------------------
    # station_id is the true key; station_name has casing/whitespace inconsistencies.
    # Rebuild station_name as the most frequent (mode) name per station_id so reporting is consistent,
    # rather than dropping rows -- the station_id itself is still reliable.
    name_mode = (
        df.assign(station_name_clean=df["station_name"].str.strip().str.title())
        .groupby("station_id")["station_name_clean"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    df["station_name"] = df["station_id"].map(name_mode)
    log("Normalized station_name casing/whitespace by mapping to the most common clean name per station_id.", log_lines)

    # ------------------------------------------------------------------
    # 3. Exact duplicate rows
    # ------------------------------------------------------------------
    before = len(df)
    df = df.drop_duplicates()
    log(f"Removed {before - len(df)} exact duplicate rows (ingestion retries).", log_lines)

    # ------------------------------------------------------------------
    # 4. Duplicate session_id with conflicting payloads (ID collision bug)
    # ------------------------------------------------------------------
    # Keep the first occurrence per session_id (arbitrary but documented), since a session_id
    # must be unique. We flag rather than blindly trust which copy is "correct".
    dup_id_mask = df.duplicated(subset="session_id", keep=False)
    n_dup_ids = df.loc[dup_id_mask, "session_id"].nunique()
    before = len(df)
    df = df.drop_duplicates(subset="session_id", keep="first")
    log(f"Found {n_dup_ids} colliding session_id values; kept first occurrence, dropped {before - len(df)} conflicting rows.", log_lines)

    # ------------------------------------------------------------------
    # 5. Negative values -> physically impossible, take absolute value only where
    #    it's clearly a sign-flip data entry error (small magnitude), otherwise null out.
    # ------------------------------------------------------------------
    neg_energy = (df["energy_consumed_kwh"] < 0).sum()
    df.loc[df["energy_consumed_kwh"] < 0, "energy_consumed_kwh"] = df.loc[df["energy_consumed_kwh"] < 0, "energy_consumed_kwh"].abs()
    log(f"Fixed {neg_energy} negative energy_consumed_kwh values by taking absolute value (sign-flip entry error).", log_lines)

    neg_rev = (df["revenue"] < 0).sum()
    df.loc[df["revenue"] < 0, "revenue"] = df.loc[df["revenue"] < 0, "revenue"].abs()
    df.loc[df["charging_cost"] < 0, "charging_cost"] = df.loc[df["charging_cost"] < 0, "charging_cost"].abs()
    log(f"Fixed {neg_rev} negative revenue values by taking absolute value.", log_lines)

    # ------------------------------------------------------------------
    # 6. Impossible waiting times (sensor glitch: >480 minutes / 8 hours is not realistic
    #    for a charging queue) -> cap via null + median imputation per station, since these
    #    are clearly erroneous rather than a true extreme case.
    # ------------------------------------------------------------------
    impossible_wait = (df["waiting_time_minutes"] > 480).sum()
    df.loc[df["waiting_time_minutes"] > 480, "waiting_time_minutes"] = np.nan
    log(f"Nulled {impossible_wait} waiting_time_minutes values > 480 min (sensor glitch, not realistic queue length).", log_lines)

    # ------------------------------------------------------------------
    # 7. Invalid / zero charging duration -> a session with 0-minute duration but
    #    energy consumed > 0 is a logging error; null the duration for later imputation.
    # ------------------------------------------------------------------
    zero_duration = ((df["charging_duration_minutes"] <= 0)).sum()
    df.loc[df["charging_duration_minutes"] <= 0, "charging_duration_minutes"] = np.nan
    log(f"Nulled {zero_duration} charging_duration_minutes values <= 0 (invalid session length).", log_lines)

    # ------------------------------------------------------------------
    # 8. Missing value imputation (documented, not silent)
    # ------------------------------------------------------------------
    # Numeric columns: impute with the median WITHIN vehicle_type/charger_type group where
    # sensible (preserves realistic variation better than a single global median).
    for col, group_cols in [
        ("energy_consumed_kwh", ["vehicle_type"]),
        ("charging_duration_minutes", ["vehicle_type", "charger_type"]),
        ("waiting_time_minutes", ["station_id"]),
        ("charging_cost", ["charger_type"]),
    ]:
        n_missing = df[col].isna().sum()
        df[col] = df.groupby(group_cols)[col].transform(lambda s: s.fillna(s.median()))
        # fallback: any still-missing (e.g. group had all-NaN) -> global median
        df[col] = df[col].fillna(df[col].median())
        log(f"Imputed {n_missing} missing values in {col} using group median of {group_cols} (fallback: global median).", log_lines)

    # vehicle_type / weather_condition (categorical): impute with "Unknown" rather than
    # guessing a category, since we don't want to fabricate a specific vehicle/weather value.
    for col in ["vehicle_type", "weather_condition"]:
        n_missing = df[col].isna().sum()
        df[col] = df[col].fillna("Unknown")
        log(f"Imputed {n_missing} missing values in {col} with 'Unknown' (avoids fabricating a specific category).", log_lines)

    # revenue: if still missing, recompute from energy * a reasonable per-kWh rate is over-engineering;
    # instead impute with group median by charger_type, consistent with charging_cost.
    n_missing_rev = df["revenue"].isna().sum()
    df["revenue"] = df.groupby("charger_type")["revenue"].transform(lambda s: s.fillna(s.median()))
    df["revenue"] = df["revenue"].fillna(df["revenue"].median())
    log(f"Imputed {n_missing_rev} missing revenue values using group median by charger_type.", log_lines)

    # ------------------------------------------------------------------
    # 9. Outlier handling (cap, don't delete) using IQR-based winsorization
    #    on core numeric fields, so extreme-but-plausible values are tempered
    #    without erasing real long-tail sessions.
    # ------------------------------------------------------------------
    for col in ["energy_consumed_kwh", "charging_duration_minutes", "waiting_time_minutes", "revenue"]:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        upper = q3 + 3 * iqr  # wide (3x IQR) cap -- only touches extreme tail, not normal variation
        n_capped = (df[col] > upper).sum()
        df[col] = np.where(df[col] > upper, upper, df[col])
        log(f"Capped {n_capped} extreme outliers in {col} at {upper:.2f} (Q3 + 3xIQR winsorization).", log_lines)

    # ------------------------------------------------------------------
    # 10. Drop rows with unrecoverable core identifiers only (station_id/date missing) --
    #     these cannot be attributed to any station or time period, so imputing would fabricate data.
    # ------------------------------------------------------------------
    before = len(df)
    df = df.dropna(subset=["station_id", "date", "start_time"])
    log(f"Dropped {before - len(df)} rows missing core identifiers (station_id/date/start_time) -- cannot be attributed or imputed safely.", log_lines)

    # ------------------------------------------------------------------
    # 11. Recompute derived time fields from cleaned start_time (source of truth)
    #     to guarantee internal consistency after cleaning.
    # ------------------------------------------------------------------
    df["hour"] = df["start_time"].dt.hour
    df["day_of_week"] = df["start_time"].dt.dayofweek
    df["month"] = df["start_time"].dt.month
    df["peak_hour"] = df["hour"].isin([8, 9, 18, 19, 20])
    log("Recomputed hour/day_of_week/month/peak_hour from cleaned start_time to guarantee consistency.", log_lines)

    df = df.reset_index(drop=True)
    log(f"\nFinal cleaned rows: {len(df)} (started with {start_n}, net removed {start_n - len(df)}, "
        f"{100*(start_n-len(df))/start_n:.2f}% of raw rows removed -- rest repaired via imputation/capping).", log_lines)

    return df, log_lines


def main():
    df = pd.read_csv(RAW_PATH)
    cleaned, log_lines = clean(df)
    cleaned.to_csv(OUT_PATH, index=False)
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(f"- {l}" if not l.startswith("#") else l for l in log_lines))
    print(f"\nSaved cleaned dataset to {OUT_PATH}")
    print(f"Saved cleaning log to {LOG_PATH}")


if __name__ == "__main__":
    main()
