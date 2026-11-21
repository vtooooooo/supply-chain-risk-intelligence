-- Which lanes account for transfer freight?
SELECT r.source,r.destination,r.transit_days,count(t.transfer_id) shipments,coalesce(sum(t.units),0) units,coalesce(sum(t.cost),0) freight FROM routes r LEFT JOIN transfers t USING(source,destination) GROUP BY 1,2,3 ORDER BY freight DESC;
