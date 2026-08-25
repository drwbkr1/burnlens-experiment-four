# Experiment Four Milestone 1 source and eligibility review

Review ID: `E4-M1-SOURCE-ADOPTION-2026-001`

Candidate package: `E4-M1-SOURCE-PACKAGE-2026-001`

Status: prepared for owner decision; no source adopted; no candidate rows
observed; no scientific source body opened.

## Decision requested

Approve, reject, or mark uncertain the exact package below as one indivisible
Milestone 1 decision. Approval releases only the bounded metadata-enumeration
actions listed here. It does not approve imagery access, event selection,
training, test opening, or release.

## Why this package

The proposed 2021-2022 window is the overlap of two publisher boundaries that
were fixed before any Experiment Four candidate row was inspected:

- NIFC states that WFIGS perimeters before 2021 are incomplete.
- MTBS states that mapping for 2023, 2024, and 2025 is still in progress.

The proposal therefore does not inspect a wider roster and then choose a
favorable date range. If the fixed window cannot supply the six excluded pilots
and 30 final events under the fixed state and ecology requirements, Milestone 1
ends `INCONCLUSIVE`.

## Exact source roles

| Role | Exact source | Use | Important limitation |
|---|---|---|---|
| Candidate universe and reference availability | USGS ScienceBase item `5e7229b8e4b01d509268afba`, MTBS Burned Areas Boundaries version 12.0, April 2025, file `mtbs_perims_DD.zip`, 374,092,911 bytes, publisher MD5 `65278fcb893f94cd0eaf66d966ee7125` | Enumerate every completed MTBS mapping in the fixed states and years before exclusions | MTBS is remote-sensing-derived, omits unmappable fires, and is not independent ground truth |
| Incident identity and maturity | NIFC WFIGS ArcGIS item `5e72b1699bf74eefb3f3aff6f4ba5511`, layer 0 | Exact IDs, state, wildfire type, final report, fire-out status, complex membership, and approved public perimeter | Dynamic source; every query and returned byte must be snapshotted and hashed |
| Landsat HLS metadata | NASA CMR concept `C2021957657-LPCLOUD`, HLSL30 version 2.0, observed revision 93, DOI `10.5067/HLS/HLSL30.002` | Anonymous granule-metadata availability only | Granule presence is not usable imagery or a quality pass |
| Sentinel-2 HLS metadata | NASA CMR concept `C2021957295-LPCLOUD`, HLSS30 version 2.0, observed revision 95, DOI `10.5067/HLS/HLSS30.002` | Anonymous granule-metadata availability only | Granule presence is not usable imagery or a quality pass |
| Ecological strata | EPA Level III Ecoregions archive `us_eco_l3.zip`, 28,424,315 bytes as observed | Dominant event-level Level III code and coverage | Broad stratification only, not pixel ecology or local management truth |

The complete 40-criterion source assessment is
`records/sources/EXPERIMENT-FOUR-SOURCE-GATE-ASSESSMENT-2026-001.json`.
Every required identity, authority, access, rights, provenance, integrity,
fitness, and privacy-security criterion passed for the stated bounded use.

## Exact eligibility proposal

- Jurisdictions: Idaho, Oregon, Washington.
- Ignition years: 2021 and 2022 only; latest eligible date 2022-12-31.
- Type: wildfire in both MTBS and the exact WFIGS identity match.
- Size: at least 1,000 acres in both MTBS mapped area and WFIGS final acres;
  no maximum-area exclusion.
- Maturity: WFIGS public, approved, visible, not deleted, valid, not
  quarantined, with final-report approval and fire-out timestamps.
- Reference metadata: the exact MTBS version 12 row exists. This proves
  reference-product availability only.
- Ecology: at least 95 percent of the MTBS boundary receives an EPA Level III
  code; dominant code is largest intersection share with lexicographic code as
  the exact-area tie break.
- HLS metadata: both HLSL30 and HLSS30 have at least one intersecting granule
  metadata record before and after the fire in the fixed broad feasibility
  intervals. No cloud, QA, scene-body, index, label, model, or metric field is
  used in Milestone 1.
- Prior experiments: all 68 bound identities remain permanently excluded.
- Unknown: any missing, conflicting, ambiguous, stale, invalid, or unadmitted
  required value is not eligible.

## Leakage and duplicate controls

- MTBS to WFIGS matching is exact ID only: IRWIN ID first, then unique fire
  identifier. Names alone never establish identity.
- One-to-one matching is required. Multiple exact WFIGS matches, duplicate
  MTBS event IDs, or duplicate non-null IRWIN IDs make every affected row
  unknown and ineligible.
- Distinct rows with geometry intersection-over-union at least 0.50 and
  ignition dates within 30 days are probable duplicates and ineligible pending
  an exact later owner decision.
- Events sharing a WFIGS complex remain distinct candidates but count as one
  selectable capacity slot; at most one can enter the study cohort.
- The MTBS intake allowlist excludes scene IDs, dNBR statistics, all severity
  thresholds, and analyst comments. WFIGS intake excludes usernames,
  personnel, costs, cause details, and unneeded operational free text.

## Capacity and terminal rule

Each state must independently provide 12 selectable slots: two future pilots
and ten future final events. The total must be 36. Each state must cover at
least two dominant Level III codes and the union at least six.

Any shortfall ends Milestone 1 `INCONCLUSIVE`. The project may not widen the
years, lower the area threshold, add states, reuse prior events, or substitute
sources to rescue the result.

## What approval releases

Approval authorizes these exact next actions under the active goal:

1. freeze the `2026-002` eligibility profile without changing a value;
2. admit the five exact source entries for the stated roles and restrictions;
3. controlled no-overwrite intake of the exact MTBS and EPA archives with
   checksum and format validation;
4. one hash-bound WFIGS 2021-2022 snapshot using the fixed field allowlist and
   absolute query;
5. anonymous CMR metadata queries for the two exact HLS collections; and
6. complete universe enumeration, capacity analysis, and independent
   Milestone 1 validation.

## What approval does not release

Approval does not authorize HLS imagery, MTBS severity rasters or thresholds,
reference labels, credentials, event selection, AOIs, role assignment,
training, inference, evaluation, test opening, scientific claims, or release.

## Decision domain

- `approve`: adopt exactly this source and eligibility package and continue the
  released Milestone 1 actions.
- `reject`: do not adopt it; stop this route and retain the bundle.
- `uncertain`: adopt nothing; return with the issue named in notes.

The required attestation is: I reviewed the exact hash-bound bundle and intend
the selected decision. Blank, implied, or general approval is not a decision.
