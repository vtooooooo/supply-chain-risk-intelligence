-- Where is inventory above the 28-day benchmark?
SELECT site,sku, avg(excess_value) average_excess_value,avg(days_supply) average_coverage FROM enriched GROUP BY site,sku ORDER BY average_excess_value DESC;
