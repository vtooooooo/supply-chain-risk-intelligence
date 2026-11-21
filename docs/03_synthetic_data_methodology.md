# Synthetic data methodology

The default run generates 548 days, 150 SKUs, 25 suppliers, and five warehouses. Seeded demand draws reflect product and site affinity, weekly and annual cycles, intermittent ordering, a promotion plan and common network shocks. Suppliers differ in promised time and probability of delay. Disruptions extend actual lead times. Some transfer lanes also realize delays.

Every day starts with scheduled arrivals. The engine fulfills demand from physical stock and records lost demand. The pre-order observation contains stock, open commitments, historical demand and completed receipts. The policy dispatches transfers and places orders. Transfers reduce the donor immediately and enter a destination pipeline until receipt. Capacity reserves all commitments, which guarantees inbound units fit even when several delayed shipments arrive together. Adjustments are zero in this model. The historical policy uses fixed order points and Monday transfers from a conservative coverage rule.

Validation checks keys, nulls, reference membership, dates, capacity at receiving and pipeline reservation, continuity, quantity conservation, and reconciliation to order, receipt and shipment events. Generator rates, latent reliability, realized future delays, and outcomes do not enter training features. Tomorrow’s promotion plan is considered known. Supplier rates shrink toward 75% before enough receipts accumulate. Days of supply floors demand at 0.15 units for predictive stability.

Units consume equal space. SKU sourcing is single-supplier. Lost sales expire, partial purchase orders are absent, and shipments have no vehicle routing or pallet constraints. Assumptions describe fictional operations.
