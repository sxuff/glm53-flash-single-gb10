# GLM-5.3 Flash DFlash2 deployment result

## Result

On one NVIDIA GB10, the new `UD-IQ2_XXS + DFlash2 Q4_K_M` deployment measured **28.9479739955 tok/s weighted server decode**, compared with **15.9611679635 tok/s** for the previous EXL3 deployment.

- Weighted server-decode ratio: **1.8136501077x**
- Weighted server-decode increase: **81.3650107666%**
- Aggregate whole-request rate: **15.6508566905 → 28.3719040665 tok/s**
- Aggregate whole-request ratio: **1.8128019844x**

## Per-workload server decode

| Workload | Previous | New | Increase |
|---|---:|---:|---:|
| Prose | 13.2363210318 | 22.0494091339 | 66.58% |
| Structured | 20.2586179225 | 39.9207548004 | 97.06% |
| Code | 16.9598108262 | 27.0730602152 | 59.63% |
| Math | 14.9848872214 | 32.0658379965 | 113.99% |

## New measured profile

- Target: `UD-IQ2_XXS`
- Drafter: `DFlash2 Q4_K_M`
- Draft settings: `n_max=3`, `n_min=0`, `p_min=0.30`
- Draft acceptance: **2,044 / 3,198**, or **63.9149468418%**
- Context allocation: 8,192 tokens
- Parallel slots: one

## Measurement contract

- Hardware: one NVIDIA GB10
- Workloads: prose, structured output, code, and math
- Generation: 400 tokens per workload
- Repetitions: one warm-up plus one measured request per workload
- Sampling: temperature 0, top-p 1, seed 42, thinking disabled

`Weighted server decode` is total measured completion tokens divided by summed server decode time. `Aggregate whole-request` is total measured completion tokens divided by summed client-observed wall time.

## Evidence boundary

This is a deployment-to-deployment comparison. The deployments use different artifacts, runtimes, and context allocations, so the result does not isolate one component. The previous deployment used a 65,536-token allocation; the new measured profile used an 8,192-token allocation.

The checked-in receipts contain timing denominators, draft acceptance, hashes, and lineage without raw generations, machine names, usernames, or local filesystem paths.
