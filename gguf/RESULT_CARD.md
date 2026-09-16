# Result-card values

## Headline

**GLM-5.3 Flash: 15.96 → 28.95 tok/s on one GB10**

## Primary metric

- Previous deployment: **15.9611679635 tok/s**
- New DFlash2 deployment: **28.9479739955 tok/s**
- Speedup: **1.8136501077x**
- Increase: **81.3650107666%**
- Label: `weighted server decode`

## Whole-request throughput

- Previous deployment: **15.6508566905 tok/s**
- New DFlash2 deployment: **28.3719040665 tok/s**
- Speedup: **1.8128019844x**
- Increase: **81.2801984430%**

## Per-workload server decode

- Prose: **13.2363210318 → 22.0494091339 tok/s**, **+66.58%**
- Structured: **20.2586179225 → 39.9207548004 tok/s**, **+97.06%**
- Code: **16.9598108262 → 27.0730602152 tok/s**, **+59.63%**
- Math: **14.9848872214 → 32.0658379965 tok/s**, **+113.99%**

## New deployment

- Target: `UD-IQ2_XXS`
- Drafter: `DFlash2 Q4_K_M`
- Settings: `n_max=3`, `n_min=0`, `p_min=0.30`
- Draft acceptance: **63.9149468418%**
- Slots: one
- Measured context allocation: 8,192 tokens

## Method footer

One GB10. Four workloads. 400 generated tokens each. One warm-up and one measured request per workload. Temperature 0, top-p 1, seed 42, thinking disabled.

## Scope label

**Deployment-to-deployment comparison, not an isolated component A/B test.**

The new result was measured with an 8K allocation. Do not label **28.95 tok/s** as a 128K-allocation measurement.

## Evidence

- [`results/deployment-comparison.json`](results/deployment-comparison.json)
- [`results/dflash2-q4km-n3-p030.json`](results/dflash2-q4km-n3-p030.json)
- [`../results/mtp-k2.json`](../results/mtp-k2.json)
