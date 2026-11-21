-- How much placed volume has arrived by reporting cutoff?
SELECT date_trunc('month',ordered) AS report_month, count(*) orders,count(received_date) received_orders,sum(o.units) ordered_units,coalesce(sum(r.units),0) received_units FROM orders o LEFT JOIN receipts r USING(order_id) GROUP BY 1 ORDER BY 1;
