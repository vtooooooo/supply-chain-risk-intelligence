-- Which products dominate fulfilled cost throughput?
WITH t AS (SELECT sku,sum(fulfilled*unit_cost) throughput FROM enriched GROUP BY sku), r AS (SELECT *, (sum(throughput) OVER(ORDER BY throughput DESC,sku)-throughput)/sum(throughput) OVER() share_before FROM t) SELECT *,CASE WHEN share_before<.8 THEN 'A' WHEN share_before<.95 THEN 'B' ELSE 'C' END abc FROM r;
