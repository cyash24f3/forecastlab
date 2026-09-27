-- Portable SQLite / PostgreSQL analysis. Bind :dataset_id rather than concatenating input.
-- Grain: one dataset + series + calendar date. Units belong to each series.

-- Daily-series summary.
SELECT series_id, COUNT(*) AS observed_days,
       MIN(date) AS first_observation, MAX(date) AS last_observation,
       SUM(value) AS observed_total, AVG(value) AS daily_mean,
       MIN(value) AS daily_min, MAX(value) AS daily_max
FROM observations
WHERE dataset_id = :dataset_id
GROUP BY series_id;

-- Leakage-safe trailing mean: current target is excluded from the window.
SELECT series_id, date, value,
       LAG(value, 7) OVER (PARTITION BY series_id ORDER BY date) AS lag_7,
       AVG(value) OVER (
         PARTITION BY series_id ORDER BY date
         ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
       ) AS preceding_7_day_mean
FROM observations
WHERE dataset_id = :dataset_id
ORDER BY series_id, date;

-- Monthly totals. ISO dates allow portable substring grouping.
SELECT series_id, SUBSTR(date, 1, 7) AS month,
       COUNT(*) AS observed_days, SUM(value) AS observed_total
FROM observations
WHERE dataset_id = :dataset_id
GROUP BY series_id, SUBSTR(date, 1, 7)
ORDER BY series_id, month;
-- Check observed_days before comparing partial months with complete months.
