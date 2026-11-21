# Executive business impact

The risk-aware policy changed nominal simulated total cost by -54.8% and fill by +13.31 percentage points. These are synthetic scenario outcomes.

Harborfield can lose sales at a constrained site while inventory sits elsewhere. SQL found donor availability elsewhere on 99.0% of shortage days. The selected 14-day model achieved test AP of 0.925. The policy combines that score with observed coverage, donor reserves, route time, destination room and marginal cost. A fixed reorder policy supplies the comparator.

## Nominal paired comparison

| Measure | Baseline | Proposed |
|---|---:|---:|
| lost cost | $451,159 | $155,645 |
| holding cost | $6,501 | $11,872 |
| transfer cost | $0 | $8,799 |
| purchase fee | $37,947 | $47,664 |
| purchase spend | $1,877,384 | $2,354,562 |
| total cost | $495,607 | $223,980 |
| working capital | $156,938 | $286,602 |
| Fill rate | 79.94% | 93.24% |
| Stockout frequency | 16.80% | 6.33% |
| Utilization | 15.57% | 28.44% |

Purchase spend represents inventory investment. The recurring cost metric includes purchase fees only. The working-capital figure is the mean closing on-hand inventory value. At cutoff, baseline and proposed physical stock were worth $152,480 and $281,968. Open purchase commitments were $273,899 and $320,890. Transfers in transit were $0 and $3,101. These gross standard-cost balances are excluded from recurring cost. Ownership and payment timing are unspecified.

## What changed the result

| Policy | Fill | Recurring cost | Purchase spend |
|---|---:|---:|---:|
| baseline | 79.94% | $495,607 | $1,877,384 |
| proposed | 93.24% | $223,980 | $2,354,562 |
| ML without transfers | 93.31% | $215,042 | $2,363,145 |
| coverage only | 90.33% | $277,039 | $2,269,310 |

The coverage-only control replaces ML scores with an observed-stock coverage score. The ML purchase-only control keeps ML prioritization and disables transfers. The full policy beats the fixed baseline in nominal service, while its higher purchase spend means the experiment does not support improved service without more purchasing. Against coverage-only, the full policy changed recurring cost by -53,058 USD. Adding transfers to the ML purchase policy changed recurring cost by +8,938 USD. The throughput and spend differences prevent attributing the baseline comparison to transfers alone.

## Sensitivity

| Scenario | Mean cost change ($) | Minimum ($) | Maximum ($) |
|---|---:|---:|---:|
| base | -271,627 | -287,406 | -249,083 |
| capacity | -264,512 | -283,675 | -231,021 |
| delays | -403,362 | -421,092 | -380,099 |
| freight | -267,037 | -281,785 | -242,853 |
| holding | -266,192 | -282,691 | -242,328 |
| penalty | -447,830 | -473,180 | -410,124 |
| volatile | -341,166 | -378,491 | -282,389 |

The range spans paired seeds and is descriptive. The policies share starting inventory, demand, promotion schedules and procurement delay draws. Purchase and transfer decisions change which draws get realized. Capacity reserves all committed arrivals. The horizon does not assign terminal pipeline value, so procurement timing can affect the comparison.

Management should compare the purchase-only and full policies in a shadow pilot. Include lane-specific service floors, transfer labor constraints and a working-capital budget. Validate effective demand, costs, capacity units and lead-time records against commercial data. Monitor calibration and backtest under actual ordering rules before granting operational authority.
