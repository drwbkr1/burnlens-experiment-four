# Milestone 1 closes INCONCLUSIVE on a frozen source shortfall

After the exact representation amendment passed, the project captured the one
approved WFIGS snapshot: 1,756 features, one page, exact approved fields,
geometry enabled, and a service edit timestamp that remained stable throughout
capture. The complete MTBS universe still contains 187 rows.

Exact identity reconciliation found 171 one-to-one WFIGS matches and 16 rows
without an exact WFIGS match. Every one of the 1,756 WFIGS snapshot features
has null `attr_FinalAcres`. Consequently, all 171 exact candidate matches have
unknown WFIGS final acreage. The frozen source package requires both MTBS
`BurnBndAc` and WFIGS `attr_FinalAcres` to be at least 1,000 acres; missing is
unknown and never eligible.

The first adapter attempt incorrectly labeled missing WFIGS final acreage as
below minimum. Its manifest remains retained at SHA-256
`d6c43363231265add24b0bf8d351b874a4e5d8c8a4370598aaab623aa7ed6490`.
The corrected no-overwrite successor uses `WFIGS_AREA_UNKNOWN` and is bound at
SHA-256
`155c6529d2e16170b44bc49c98f9cb5325ad34d7a78d8b0628bba40ff62c2246`.

The complete candidate manifest binds all 187 unique candidates and exact MTBS
geometry records. None can proceed to ecology or HLS checks, so the maximum
selectable capacity is zero in Idaho, Oregon, and Washington. Additional
queries cannot rescue a missing required antecedent and were not run.

Independent validation replayed source counts, candidate IDs, geometry hashes,
and deterministic evaluator outputs with no errors. The engineering evidence
passes; the frozen Milestone 1 result is `INCONCLUSIVE`. No pilot or final event
was selected, no HLS imagery or label was opened, and Milestone 2 is not
authorized.
