-- Where are concurrent stock imbalances concentrated?
WITH gaps AS (SELECT sku,date,max(days_supply)-min(days_supply) gap FROM enriched GROUP BY sku,date) SELECT sku,avg(gap) average_coverage_gap,max(gap) largest_gap FROM gaps GROUP BY sku ORDER BY average_coverage_gap DESC;
