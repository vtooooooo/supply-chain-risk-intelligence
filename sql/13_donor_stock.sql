-- How often can closing donor stock cover unmet demand?
SELECT site,count(*) stockout_days,count_if(other_stock>=lost) coverable_days,sum(lost_cost) FILTER(WHERE other_stock>=lost) coverable_cost FROM enriched WHERE lost>0 GROUP BY site ORDER BY coverable_days DESC;
