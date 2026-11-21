-- Which suppliers deliver least consistently?
SELECT supplier,avg(lead_days) mean_days,stddev_samp(lead_days) sd_days,quantile_cont(lead_days,.9) p90 FROM supplier_lead_history GROUP BY supplier ORDER BY sd_days DESC;
