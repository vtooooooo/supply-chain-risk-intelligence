# Harborfield case study

**Problem.** Regional stockouts coexist with network stock. Finance needs to know whether redistribution warrants its cost.

**Data.** A chronological synthetic event ledger connects demand, fulfillment, receipts and transfers across five warehouses.

**Investigation.** Network fill was 85.27%. Other locations held enough closing units on 99.0% of shortage pair-days, before lead times and reserves.

**Modeling.** The selected lightgbm_31 model reached test average precision of 0.925 in a purged chronological split.

**Decisions.** The heuristic applies finite capacity, priced freight, transit time and donor reserves to transfer and purchase proposals.

**Results and business value.** Nominal synthetic fill moved from 79.94% to 93.24%. Cost changed -54.8%. A field pilot should test lane economics and service with independently verified inputs.
