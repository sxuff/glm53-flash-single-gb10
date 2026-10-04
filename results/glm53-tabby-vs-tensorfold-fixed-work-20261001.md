# TabbyAPI vs TensorFold, original-test comparison

Measured short fixed-work decode improvement versus fresh TabbyAPI recipe, not a replacement: incomplete context/capability envelope; previous six-task statistical nonqualification remains unchanged.

## Protocol
- Single GB10; same installed GLM-5.3-Flash 2.05-bpw checkpoint, revision51058cd551c7e570d87bd32a4adee720edce2349.
- Fresh TabbyAPI ExLlamaV3 1.5.2 MTP1, original262K FP16 vision-enabled recipe; raw TensorFold TP1 MTP1, tested2051dense-only context.
- Exact original4workloads, greedy andtemp0.6/top_p0.95, one warmup plus3measured,400forced tokens. Original15answer High andzero-budget panels,3loop cases8192cap,256quick tests,84865prefill,tools,vision.
- Frozen input IDs include Tabby default BOS. Live apply-template and usage input counts verified. Server default High preserved for omittedeffort.
- Decode normalized outputminusfirst / enginefirsttolast window. Tabby duration rounded0.01seconds; legacyrates retained. WireTTFT andengineTTFT are not interchangeable. Speed panel measures fixed work, not finished code correctness.
- Tabby ignores submitted seeds, as historical API did. Greedy cells controlled; sampled repeats exploratory, not paired-seed identity.

## Decode medians, tok/s. Three repeats per cell.
- greedy / code: Tabby 29.71, TensorFold 31.68, +6.6%.
- greedy / math: Tabby 28.40, TensorFold 31.56, +11.1%.
- greedy / prose: Tabby 25.66, TensorFold 31.03, +20.9%.
- greedy / structured: Tabby 31.42, TensorFold 35.35, +12.5%.
- temp0.6_top_p0.95 / code: Tabby 28.04, TensorFold 31.45, +12.2%.
- temp0.6_top_p0.95 / math: Tabby 28.40, TensorFold 31.51, +10.9%.
- temp0.6_top_p0.95 / prose: Tabby 26.53, TensorFold 29.75, +12.1%.
- temp0.6_top_p0.95 / structured: Tabby 31.39, TensorFold 34.77, +10.8%.

## Pooled fixed-work rates
- greedy: Tabby 28.64, TensorFold 32.32 tok/s, +12.9%.
- temp0.6_top_p0.95: Tabby 28.49, TensorFold 31.75 tok/s, +11.5%.
- both: Tabby 28.56, TensorFold 32.03 tok/s, +12.1%.

## Answers and capability limits
- Original High known-answer panel:15/15 both arms. Small deterministic smoke panel, not broad quality noninferiority.
- Prior six-task120samples/arm study remains statistically nonqualified; this narrower panel does not overturn it.
- Original long-form prose: Tabby3/3; TF1/3 completed,2requests reached actual dense boundary at2010outputtokens. Preserve fullraw outputs; classify unsupported rather than equivalent semantic failure.
- TF records22unsupported primarycases:15zero-budget,2quick256budget0,1longprefill,2tool/vision,2dense-boundary prose. Fortyprimarycases generated successfully; all62requestedkeys present.
- Tabby completed uncached84865token prefill at356.61prompttok/s,237.98s prompttime. This does not validate full262K actualpromptdepth. Tool andvision literalcanaries passed. TF doesnotimplement these capabilities in thisport.

## Integrity and closure
- Each arm validates62primary plus10warmup keys, zero duplicates or missing keys. TFwarmups include2unsupportedbudget0entries.
- Tabby57primary+8warmup measurements retained from firstblock; continuation5primary+2warmup requests only. Rejectedquickwarmup generatedzero tokens and remains in priorwarmupjournal. No completedspeedcell repeated.
- Preparationfailure caused bare rendererMax vs effective serverHigh; correction changed freezer only, not originalrequest/config.
- Postcollection driver analyzed priorroot bymistake. Invalidaggregation retained; CPU-only correct-root analysis rerun. No GPU repetitions.
- Source seal unchanged. Experiment swap0throughout; minimum wholehostMemAvailable24.09GiB vs20GiBfloor. TFpeakCUDAallocated79.67GiB.
- Qwen backend andbothproxies restored, one authenticated finalgeneration answered Hello! How can I help you today? No experimentcontainers remain.
- No original runtime/model edits, commits, pushes or posts.

## Lineage
- OriginalTensorFold pin9cd52ab4daba68ddd09be89be8f23ad43175e821; originalExLlamaV3 pin12414d0af7b3beeabdda5990f6b554b996fa1416; unchangedoriginalgenericEXL3kernels reused.
- TabbyAPI sourcef07131cd8fe34e449fe87cdd3a066b52b96d3cac; immutable image sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee.
- Newintegration is isolatedcorpus/renderfreeze, HTTPandrawportcollectors, actualpositionbudgetguard, common-clock analysis and supervisedcontinuation. No vendor invention claim.

## Evidence
- Canonical summary:RESULTS.json; protocol.json; tabby-remaining.json; seal.json; runs/.
- Retained firstblock:../tabby-comparison-v33/runs/tabbyapi_mtp/{rows.jsonl,warmup.jsonl}; continuationroot carriesonlyremainingTabbyrows pluscompleteTensorFoldarm.
- Historicalsource paths, recoveredmessageIDs andhashes in corpus.PROVENANCE. Historicalheadlines are not controls.
