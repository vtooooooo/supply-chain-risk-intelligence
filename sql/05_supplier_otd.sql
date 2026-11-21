-- Which suppliers miss commitments?
SELECT supplier,count(*) receipts, avg((received_date<=promised)::INT) on_time FROM supplier_lead_history GROUP BY supplier ORDER BY on_time;
