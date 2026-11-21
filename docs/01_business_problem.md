# Harborfield Consumer Goods

Harborfield is a fictional US CPG manufacturer. Its five distribution centers can collectively have enough stock while one region loses sales. Location, transit time, available storage, and the donor's own demand determine whether that stock can help.

The Supply Chain Director sets service and cost goals. Inventory Planning allocates safety stock and approves rebalance plans. Procurement manages supplier commitments and contingencies. Warehouse Operations controls receiving and dispatch capacity. Finance values inventory and evaluates the cost of service failures.

## Research questions

1. How often can another site cover a local shortage?
2. Which SKU and site pairs account for the most lost contribution?
3. What inventory value exceeds 28 days of recent demand?
4. Which suppliers are late or have volatile lead times?
5. How do seasonal, regional, and volatile demand patterns coincide with shortages?
6. When do transfers cost less than emergency replenishment?
7. Which recommendations survive higher freight costs?
8. Which pairs should planners review first?
9. How do demand shocks and supplier delays affect service?
10. How do cost and working capital change when the policy changes?

Test the association of supplier delays with shortages, the prevalence of coincident donor stock, and whether redistribution improves service and total cost under matched experiments. A contemporaneous donor balance is an upper bound on actionable opportunity.

## Measures

| KPI | Definition |
|---|---|
| Fill rate | Sum fulfilled units divided by sum requested units |
| Stockout frequency | Share of pair-days with unmet positive demand |
| Duration | Consecutive pair-days with unmet demand |
| Turnover | Fulfilled units valued at standard cost divided by mean closing inventory value over the reported period |
| Days of supply | Closing units divided by trailing mean daily demand, undefined at zero demand |
| Excess | Positive closing units above 28 days of trailing mean demand |
| On-time delivery | Received orders arriving by promised date divided by received orders |
| Lead-time variability | Sample standard deviation of observed order-to-receipt days |
| Holding cost | Daily closing units multiplied by daily carrying cost |
| Lost sales | Unfulfilled units multiplied by SKU lost contribution penalty |
| Transfer cost | Shipped units multiplied by route cost |
| Total cost | Holding, lost contribution, transfer freight, and incremental procurement fees |

Aggregate rates from their numerators and denominators. Unfilled requests expire daily as lost sales. Working capital uses standard purchase cost. The cost objective includes incremental procurement fees and excludes standard purchase cost to avoid counting inventory investment as a recurring expense.
