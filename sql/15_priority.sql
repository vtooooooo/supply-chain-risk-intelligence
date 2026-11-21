-- Which active pairs lead trailing loss exposure?
SELECT site,sku,sum(lost_cost) trailing_loss,rank() OVER(ORDER BY sum(lost_cost) DESC) priority FROM daily WHERE date>(SELECT max(date)-INTERVAL 28 DAY FROM daily) GROUP BY site,sku ORDER BY priority,site,sku;
