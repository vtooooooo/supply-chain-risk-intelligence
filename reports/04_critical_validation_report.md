# Critical validation report

**Verdict.** Ready for a professional Data Analyst or Data Scientist portfolio as a reproducible synthetic case study. The strongest story is the comparison across policies and the finding that adding transfers raised recurring cost in the nominal experiment. The project still needs real transaction data, external model validation, an inventory budget and an operational pilot before it can support live decisions. [Project overview](../README.md)

## 1. Model validity

The label is any positive unmet demand at a warehouse-SKU on days `t+1` through `t+14`. Historical daily stockout prevalence was 11.75%, while held-out 14-day prevalence was **58.48%**. A constant score therefore gets 0.585 average precision (AP). The rules score reaches **0.895**, physical days of supply alone reaches **0.870**, and the validation-selected LightGBM reaches **0.925**. Logistic regression reached 0.9254, just ahead of LightGBM's 0.9245 on the held-out period. Model selection remains based on validation AP. [Model code](../src/model.py) · [Evaluation](02_model_evaluation.md)

| Split | Observation dates | Rows | Positive labels |
|---|---|---:|---:|
| Train | Jan 28–Nov 9, 2024 | 215,250 | 44.36% |
| Validation | Nov 24, 2024–Feb 27, 2025 | 72,000 | 48.62% |
| Test | Mar 14–Jun 17, 2025 | 72,000 | 58.48% |

The latest target in train ends Nov 23, and the latest validation target ends Mar 13. Both end before the next split begins. The scoring point is after arrivals and that day's fulfillment, before transfers or ordering. Features use opening commitments, pre-order stock, trailing demand, completed receipts, promised purchase dates and the assumed known next-day promotion plan. The open-PO filter drops orders that arrived by the observation date. It does not encode their later realized arrival date. Trailing shortage frequency includes the current day because scoring follows fulfillment. Subsequent unmet demand contributes only to labels. The feature list excludes latent demand rates, realized disruption flags and future receipts. The leakage regression changes future losses and verifies that earlier features remain identical. An independent SQL reconstruction across 1,540 sampled rows found zero mismatches in open PO units, PO units due by promise, trailing mean demand or pre-order stock. This audit found no look-ahead in the scored feature path. [Feature preparation](../src/model.py) · [Event ordering](../src/operations.py) · [Leakage test](../tests/test_pipeline.py)

Adjacent labels share 13 of 14 days and agree 97.48% of the time within a pair. The 72,000 test rows should not be treated as independent. Taking every 14th date and repeating for all 14 offsets gave AP ranges of **0.877–0.909** for rules and **0.914–0.929** for LightGBM, with ML ahead by 0.019–0.037. Each offset removes window overlap within the pair. Those ranges are sensitivity checks because offsets share data and network shocks affect multiple pairs at once. [Audit calculations](../scripts/audit.py)

The lowest days-of-supply quintile had 91.22% positive labels versus 3.93% in the highest. Inventory is a direct input to fulfillment, and the simulator combines a fixed replenishment policy with persistent SKU, site and supplier characteristics. This yields persistent, mechanically predictable stockout risk. The rules score exploits that structure. Selection lift is modest against a strong baseline and the holdout uses the same synthetic network and generator. No real-world discrimination or calibration is established. [Synthetic methodology](../docs/03_synthetic_data_methodology.md)

## 2. Working capital and financing

The proposed policy uses site-level trailing demand, supplier variability and predicted risk to set replenishment buffers. The fixed policy uses a SKU-level nominal demand rate shared across sites. In the nominal comparisons, procurement spend increased **$477,178** through more buying and received inventory. Average physical utilization rose from 15.57% to 28.44%, and average on-hand value increased **$129,663**, or **82.6%**, from $156,938 to $286,602. The average extra on-hand balance ranged from $115,262 to $156,811 across the three nominal seeds. Gross procurement spend is a flow, so it cannot also be counted as incremental balance-sheet investment. [Executive reconciliation](03_business_impact_report.md) · [Policy logic](../src/optimization/__init__.py)

Over 56 days, modeled lost contribution fell by $295,514. Incremental holding cost was $5,371, freight $8,799 and purchase fees $9,717, yielding **$271,627** of modeled recurring savings. Holding already uses 27% annualized on average physical stock. The table adds financing on the extra balance as a conservative surcharge when the 27% is interpreted as non-financing carrying cost. If the 27% already includes finance, use the existing holding charge or replace its finance component to avoid double counting. [Cost implementation](../src/operations.py)

| Annual financing surcharge | Extra cost over 56 days | Nominal savings after surcharge |
|---:|---:|---:|
| 5% | $995 | $270,632 |
| 10% | $1,989 | $269,637 |
| 15% | $2,984 | $268,643 |
| 20% | $3,979 | $267,648 |
| 30% | $5,968 | $265,659 |

At a 15% surcharge, covering the extra holding, fees, freight and financing requires realizing about **9.1%** of the simulated avoided lost contribution. The modeled margin covers the investment hurdle under those assumptions. This is a 56-day economic sensitivity, with no annualization or cash-flow payback claim. Payment terms, discounts, demand recapture and economically realizable margin are unresolved. Average physical stock also excludes supplier financing and pipeline title. [Audit calculations](../scripts/audit.py)

## 3. Why purchase-only was stronger

With the same nominal seeds and ML purchasing logic, disabling transfers yielded **93.31% fill** versus **93.24%** and **$215,042** recurring cost versus **$223,980**. Adding transfers increased recurring cost by **$8,938** on average, with increases of $7,383 to $12,047 across all three seeds. It reduced mean working capital by **$12,421** and buying spend by **$8,584**. The recurring cost change reconciles to $8,799 more freight and $812 more lost contribution, offset by $515 less holding and $158 fewer purchase fees. Two seeds showed less lost contribution with transfers, while the third showed a $4,245 increase. [Paired policy audit](../scripts/audit.py)

I traced allocation and replay through donor stock, destination reservations, positive transit times, purchase triggers and the daily ledger. The evidence points to **an economic tradeoff amplified by the heuristic**. Transfer ranking treats probability of any 14-day loss as a per-unit proxy for avoided contribution. It discounts promised transit time but does not model the units that will miss service before arrival, donor opportunity cost beyond a nine-day reserve, or the effect of a late inbound transfer delaying a replenishment trigger. Shipment commitments immediately enter destination inventory position. Some transfers substitute for purchases and reduce capital, but that benefit did not pay for freight in the nominal runs. No transfer conservation or scheduling defect explained the control result. The finding covers three nominal seeds and does not establish whether purchase-only dominates in stressed lanes. [Optimizer](../src/optimization/__init__.py) · [Decision methodology](../docs/05_optimization_methodology.md)

## 4. All 21 comparisons

Means and observed ranges use three paired seeds per scenario. Each cell with brackets shows the minimum and maximum of the three paired results. Cost reduction uses each pair's baseline cost as denominator. [Experiment code](../src/experiment.py) · [Audit calculations](../scripts/audit.py)

| Scenario | Mean baseline → proposed fill | Fill gain, percentage points | Recurring cost reduction, % | Savings, USD |
|---|---:|---:|---:|---:|
| Nominal | 79.94% → 93.24% | 13.31 [12.61, 13.95] | 54.76 [52.66, 56.82] | 271,627 [249,083, 287,406] |
| Capacity −32% | 79.94% → 92.37% | 12.44 [10.76, 13.48] | 53.27 [48.84, 56.08] | 264,512 [231,021, 283,675] |
| Supplier delay +4 days | 63.48% → 82.74% | 19.25 [18.74, 19.62] | 47.18 [46.65, 48.06] | 403,362 [380,099, 421,092] |
| Freight ×2 | 79.94% → 93.24% | 13.30 [12.57, 13.90] | 53.83 [51.34, 55.71] | 267,037 [242,853, 281,785] |
| Holding ×2 | 79.94% → 93.20% | 13.26 [12.57, 13.92] | 52.96 [50.53, 55.19] | 266,192 [242,328, 282,691] |
| Stockout penalty ×1.6 | 79.94% → 93.26% | 13.32 [12.53, 13.96] | 58.39 [56.16, 60.47] | 447,830 [410,124, 473,180] |
| Demand volatility ×2 | 75.50% → 91.02% | 15.52 [13.64, 16.54] | 52.99 [49.57, 55.34] | 341,166 [282,389, 378,491] |
| **All 21** | | **14.34 [10.76, 19.62]** | **53.34 [46.65, 60.47]** | **323,104 [231,021, 473,180]** |

Cost and fill improved in all 21 comparisons, while additional average working capital ranged from **$82,183 to $228,360**. The worst percentage cost gain was delay seed 205. The worst dollar savings and fill gain were capacity seed 205. The lowest absolute proposed fill was **82.39%** in delay seed 309, with a **16.15%** pair-day stockout rate. Larger dollar savings under delays and higher penalties reflect larger baseline losses or a higher valuation of lost units. Across the three seeds, the seven-scenario average cost improvement ranged from **50.82% to 55.20%**. These are descriptive stress and seed ranges. Three seeds, reused across scenarios, cannot support a precise confidence interval or deployment-level risk estimate. [Executive report](03_business_impact_report.md)

## 5. Ledger and end-of-horizon validity

The full history reconciled **411,000** daily rows, **51,765** POs, **50,999** observed receipts and **3,595** transfers. Of the transfers, **331** arrived later than promised and **56** were still in transit at cutoff. Each day fulfilled the lesser of demand and physical inventory after arrivals. Unfilled demand expired. The audit checked opening/closing continuity, exact PO and receipt quantities, PO lead times, transfer transit chronology, site-level receiving peaks and capacity reserved for committed arrivals. The validator also ran on both policies across all scenarios and on the nominal controls. Policy pairs started from the same inventory, realized the same demand and used common supplier and lane delay inputs within each seed and scenario. [Warehouse checks](../src/warehouse.py) · [Simulation](../src/operations.py)

| Mean nominal cutoff balance at standard cost | Baseline | Proposed |
|---|---:|---:|
| Closing on-hand | $152,480 | $281,968 |
| Unreceived PO commitments | $273,899 | $320,890 |
| Transfers in transit | $0 | $3,101 |
| Gross total | $426,379 | $605,959 |

The **$179,580** larger cutoff balance or commitment under the proposed policy matters for liquidity. Gross PO commitments do not establish ownership, payment timing or recoverable value. Recurring cost includes order fees when orders are placed and excludes purchase principal and terminal valuation. The comparison also excludes service earned after day 56, terminal pipeline carrying cost and salvage or liquidation. A steady-state or run-off experiment would be needed for a cash-flow or investment decision. The capacity rule reserves all outstanding arrivals, and the cold-start comparison, single sourcing and unit-based capacity simplify real planning. [Terminal reporting](03_business_impact_report.md) · [KPI implementation](../src/experiment.py)

## 6. Analytical completeness and fixes

- All **15 SQL queries** were executed again and reconciled to the CSVs. The report includes the business question, a returned row and the operational interpretation. In SKU rollups the SQL field `stockout_days` counts warehouse-SKU-days across sites, so it can exceed the number of calendar days. The donor-stock result is end-of-day physical availability before feasibility constraints. It should not be interpreted as recoverable sales. [SQL findings](../docs/04_sql_analysis_findings.md)
- All **five notebooks** were rerun. Ten code cells had execution counts and zero error outputs. The output exercises profiling, actual demand and supplier patterns, the moving-block interval, classification results, calibration and subgroup and feature diagnostics. The supplier Spearman coefficient of 0.64 is descriptive, confounded by the product mix and based on completed receipts. The moving-block interval describes donor availability under the synthetic generator. [Notebooks](../notebooks/) · [Exploratory report](01_exploratory_analysis_report.md)
- The model and executive reports were regenerated from persisted outputs. Costs and service values in all 42 replay rows and six nominal control rows matched the pre-review values exactly. The valuation additions appear as separate balances. [Model evaluation](02_model_evaluation.md) · [Executive report](03_business_impact_report.md)
- Fixed the one-day replay failure on empty date columns. Added checks for incomplete daily grids, fulfillment against available stock, commitment and position reconciliation, and out-of-period receipt and shipment records. Added terminal value fields and regression coverage. The app now displays the promised arrival in the recommendation and download. Realized arrival remains in the historical artifact for audit. [Validator](../src/warehouse.py) · [Tests](../tests/test_pipeline.py) · [App](../app/Home.py)

## 7. Production verification

- **Local full and reduced pipelines:** completed successfully. The full notebook and report stage and the reduced CI-equivalent workflow ran. **16 tests passed** on both datasets, including all eight app views, a submitted scenario, and the new regression checks. Both suites emitted 13 third-party Matplotlib deprecation warnings.
- **Container:** rebuilt the reviewed source and started Streamlit locally. The health endpoint returned `ok`, and the image included the transfer-date display fix. The independent build reproduced held-out predictions exactly and matched 23 CSV exports within floating-point tolerance.
- **Hosted CI and deployment:** workflow YAML parsed with push and pull request triggers, and its commands ran locally. Hosted Actions execution and public deployment were outside the verified environment. The base image tag can move, and the dependency manifest pins direct packages only. Image digest and transitive dependency locking remain production hardening gaps, along with access control, telemetry, model drift monitoring and an operational data contract. [Dockerfile](../Dockerfile) · [CI workflow](../.github/workflows/ci.yml)

To reproduce the audit from the project root with the development environment active:

```bash
python -m scripts.run
python -m scripts.analyze
python -m scripts.audit
pytest -q
```
