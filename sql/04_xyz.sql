-- Which products have variable network demand?
WITH t AS (SELECT date,sku,sum(demand) demand FROM daily GROUP BY date,sku), r AS (SELECT sku,stddev_samp(demand)/nullif(avg(demand),0) cv FROM t GROUP BY sku) SELECT *, CASE WHEN cv<.35 THEN 'X' WHEN cv<.7 THEN 'Y' ELSE 'Z' END xyz FROM r ORDER BY cv DESC;
