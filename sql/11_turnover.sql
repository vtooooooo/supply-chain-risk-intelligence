-- How fast does inventory turn during each month?
SELECT date_trunc('month',date) AS report_month, sum(fulfilled*unit_cost)/(sum(inventory_value)/count(DISTINCT date)) turnover FROM enriched GROUP BY 1 ORDER BY 1;
