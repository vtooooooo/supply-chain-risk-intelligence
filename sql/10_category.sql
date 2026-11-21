-- Which categories have the greatest contribution exposure?
SELECT category,sum(lost_cost) lost_cost,sum(holding_cost) holding_cost,sum(fulfilled)/sum(demand) fill_rate FROM enriched GROUP BY category ORDER BY lost_cost DESC;
