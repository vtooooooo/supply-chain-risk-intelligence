# Résumé and interview notes

## Analyst bullets

- Built a reconciled DuckDB supply-chain warehouse and 15 SQL diagnostics, measuring 85.27% historical fill across a synthetic five-site network.
- Quantified donor inventory coinciding with 99.0% of shortage pair-days and evaluated paired financial and service tradeoffs.

## Data scientist bullets

- Trained a point-in-time 14-day stockout classifier with 0.925 held-out average precision and chronological horizon purging.
- Combined predictions with constrained dispatch and procurement, measuring -54.8% nominal synthetic cost change in matched scenario replay.

## 60-second explanation

Harborfield loses sales when product is in the wrong region. I simulated its ledger, reconciled every inventory movement, and used SQL and statistical analysis to quantify the mismatch. I scored future shortages from information available at ordering time and translated scores into inventory decisions. I then replayed both policies on paired demand and delay scenarios and compared service, costs and working capital.

## Technical explanation

Observation is after demand and before ordering. Labels examine days 1 through 14. Split boundaries purge training and validation outcomes that reach the next period. The decision heuristic sorts eligible lane-SKU candidates by expected marginal benefit, then allocates only available donor and capacity units. The experiment varies scenarios and reuses exogenous draws within each pair.

## Interview questions

1. **How did you detect leakage?** Enforce label cutoffs and build features from the snapshot and completed receipts.
2. **Why average precision?** It summarizes precision-recall discrimination on the shortage class.
3. **Can another site's stock always help?** Transit, donor buffers, destination room and freight limit eligibility.
4. **How did you compare policies?** Matched dates, initial stock, constraints and exogenous random seeds.
5. **What would you validate next?** Confirm demand censoring, unit volume, supplier risk and costs before a shadow pilot.
