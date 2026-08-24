# Data Cleaning Log

- Starting rows: 85850
- Standardized energy_consumed_kwh to numeric (stripped stray unit text).
- Parsed date/start_time/end_time to datetime; unparseable values become NaT for review.
- Normalized station_name casing/whitespace by mapping to the most common clean name per station_id.
- Removed 848 exact duplicate rows (ingestion retries).
- Found 100 colliding session_id values; kept first occurrence, dropped 100 conflicting rows.
- Fixed 338 negative energy_consumed_kwh values by taking absolute value (sign-flip entry error).
- Fixed 339 negative revenue values by taking absolute value.
- Nulled 170 waiting_time_minutes values > 480 min (sensor glitch, not realistic queue length).
- Nulled 255 charging_duration_minutes values <= 0 (invalid session length).
- Imputed 848 missing values in energy_consumed_kwh using group median of ['vehicle_type'] (fallback: global median).
- Imputed 255 missing values in charging_duration_minutes using group median of ['vehicle_type', 'charger_type'] (fallback: global median).
- Imputed 1865 missing values in waiting_time_minutes using group median of ['station_id'] (fallback: global median).
- Imputed 850 missing values in charging_cost using group median of ['charger_type'] (fallback: global median).
- Imputed 425 missing values in vehicle_type with 'Unknown' (avoids fabricating a specific category).
- Imputed 2545 missing values in weather_condition with 'Unknown' (avoids fabricating a specific category).
- Imputed 0 missing revenue values using group median by charger_type.
- Capped 0 extreme outliers in energy_consumed_kwh at 83.18 (Q3 + 3xIQR winsorization).
- Capped 2196 extreme outliers in charging_duration_minutes at 635.00 (Q3 + 3xIQR winsorization).
- Capped 712 extreme outliers in waiting_time_minutes at 42.60 (Q3 + 3xIQR winsorization).
- Capped 20 extreme outliers in revenue at 1005.64 (Q3 + 3xIQR winsorization).
- Dropped 0 rows missing core identifiers (station_id/date/start_time) -- cannot be attributed or imputed safely.
- Recomputed hour/day_of_week/month/peak_hour from cleaned start_time to guarantee consistency.
- 
Final cleaned rows: 84902 (started with 85850, net removed 948, 1.10% of raw rows removed -- rest repaired via imputation/capping).