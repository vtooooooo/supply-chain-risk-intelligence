-- How does service vary by region?
SELECT site, sum(fulfilled)/sum(demand) fill_rate, avg((lost>0)::INT) stockout_rate, sum(lost_cost) lost_cost, sum(inventory_value)/count(DISTINCT date) average_inventory FROM daily GROUP BY site ORDER BY lost_cost DESC;
