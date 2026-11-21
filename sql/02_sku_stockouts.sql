-- Which SKUs lose sales most often?
SELECT sku, count_if(lost>0) stockout_days, sum(lost) lost_units, sum(lost_cost) lost_cost FROM daily GROUP BY sku ORDER BY lost_cost DESC;
