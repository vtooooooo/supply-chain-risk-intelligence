# Executed SQL findings

Network fill was 85.27%. The historical ledger reported $2,736,339 in lost contribution.



## 01 warehouse

How does service vary by region?

Executed output has 5 rows. Fields are site, fill_rate, stockout_rate, lost_cost, average_inventory.

The first reported row is site=1.0, fill_rate=0.8042285513107915, stockout_rate=0.1674452554744525, lost_cost=854206.8300000003, average_inventory=30887.76520072987.

Compare weighted regional fill with mean inventory to identify service gaps.

See `sql/01_warehouse.sql` for the query.



## 02 sku stockouts

Which SKUs lose sales most often?

Executed output has 150 rows. Fields are sku, stockout_days, lost_units, lost_cost.

The first reported row is sku=97.0, stockout_days=602.0, lost_units=4505.0, lost_cost=104696.2.

Rank products by accumulated loss to prioritize the largest exposures.

See `sql/02_sku_stockouts.sql` for the query.



## 03 abc

Which products dominate fulfilled cost throughput?

Executed output has 150 rows. Fields are sku, throughput, share_before, abc.

The first reported row is sku=33, throughput=395951.95000000135, share_before=0.0, abc=A.

Apply cumulative 80% and 95% throughput cutoffs for differentiated review cadence.

See `sql/03_abc.sql` for the query.



## 04 xyz

Which products have variable network demand?

Executed output has 150 rows. Fields are sku, cv, xyz.

The first reported row is sku=34, cv=1.1326002725325908, xyz=Z.

Use the coefficient of variation of daily network demand to distinguish stable and volatile SKUs.

See `sql/04_xyz.sql` for the query.



## 05 supplier otd

Which suppliers miss commitments?

Executed output has 25 rows. Fields are supplier, receipts, on_time.

The first reported row is supplier=22.0, receipts=1999.0, on_time=0.5477738869434717.

Compare received orders to promised dates to focus supplier follow-up.

See `sql/05_supplier_otd.sql` for the query.



## 06 lead variability

Which suppliers deliver least consistently?

Executed output has 25 rows. Fields are supplier, mean_days, sd_days, p90.

The first reported row is supplier=0.0, mean_days=12.749224405377456, sd_days=2.4494236192485945, p90=17.0.

Compare dispersion and the upper tail of realized lead times when setting buffers.

See `sql/06_lead_variability.sql` for the query.



## 07 imbalance

Where are concurrent stock imbalances concentrated?

Executed output has 150 rows. Fields are sku, average_coverage_gap, largest_gap.

The first reported row is sku=80.0, average_coverage_gap=99.35960528199496, largest_gap=305.8579234972678.

Measure each date's best-versus-worst coverage spread and prioritize persistent gaps.

See `sql/07_imbalance.sql` for the query.



## 08 excess

Where is inventory above the 28-day benchmark?

Executed output has 750 rows. Fields are site, sku, average_excess_value, average_coverage.

The first reported row is site=0.0, sku=54.0, average_excess_value=739.7798771074708, average_coverage=87.02142339824053.

Value daily positive excess against 28 days of trailing demand, then average exposure.

See `sql/08_excess.sql` for the query.



## 09 lost sales

How much lost contribution varies month to month?

Executed output has 95 rows. Fields are report_month, site, lost_units, lost_cost.

The first reported row is report_month=2024-01-01, site=0, lost_units=1206.0, lost_cost=10065.249999999998.

Track month-by-region unmet units and contribution loss to distinguish cost from volume.

See `sql/09_lost_sales.sql` for the query.



## 10 category

Which categories have the greatest contribution exposure?

Executed output has 5 rows. Fields are category, lost_cost, holding_cost, fill_rate.

The first reported row is category=2.0, lost_cost=623383.050000004, holding_cost=12762.176688492907, fill_rate=0.8419656089940396.

Compare contribution lost and carrying cost by category with observed fill.

See `sql/10_category.sql` for the query.



## 11 turnover

How fast does inventory turn during each month?

Executed output has 19 rows. Fields are report_month, turnover.

The first reported row is report_month=2024-01-01, turnover=5.182050724602915.

Divide cost of fulfilled units by mean closing valuation per month for period turnover.

See `sql/11_turnover.sql` for the query.



## 12 replenishment

How much placed volume has arrived by reporting cutoff?

Executed output has 19 rows. Fields are report_month, orders, received_orders, ordered_units, received_units.

The first reported row is report_month=2024-01-01, orders=3186, received_orders=3186, ordered_units=108408.0, received_units=108408.0.

Use the order cohort and receipt linkage to track open volume as of cutoff.

See `sql/12_replenishment.sql` for the query.



## 13 donor stock

How often can closing donor stock cover unmet demand?

Executed output has 5 rows. Fields are site, stockout_days, coverable_days, coverable_cost.

The first reported row is site=1.0, stockout_days=13764.0, coverable_days=13654.0, coverable_cost=844209.7200000015.

Compare unmet units to other sites' concurrent closing stock to estimate the upper bound on redistribution.

See `sql/13_donor_stock.sql` for the query.



## 14 transfer cost

Which lanes account for transfer freight?

Executed output has 20 rows. Fields are source, destination, transit_days, shipments, units, freight.

The first reported row is source=0.0, destination=4.0, transit_days=5.0, shipments=523.0, units=3484.0, freight=4424.6799999999885.

Join all valid lanes to shipment records to retain unused routes and quantify freight concentration.

See `sql/14_transfer_cost.sql` for the query.



## 15 priority

Which active pairs lead trailing loss exposure?

Executed output has 750 rows. Fields are site, sku, trailing_loss, priority.

The first reported row is site=4.0, sku=148.0, trailing_loss=3315.46, priority=1.0.

Rank pair-level cost over the latest 28 days for planner triage.

See `sql/15_priority.sql` for the query.
