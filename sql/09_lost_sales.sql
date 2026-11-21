-- How much lost contribution varies month to month?
SELECT date_trunc('month',date) AS report_month, site,sum(lost) lost_units, sum(lost_cost) lost_cost FROM daily GROUP BY 1,2 ORDER BY 1,2;
