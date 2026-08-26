# Milestone 1 literal-encoding amendment — owner review

## Decision requested

Approve, reject, or mark uncertain one exact representation-only amendment to
the frozen metadata protocol. No event is being selected, and no scientific
claim is being reviewed.

## What the live sources actually contain

- The WFIGS 2021–2022 window has **0** rows whose `attr_POOState` is exactly
  `ID`, `OR`, or `WA`, and **1,756** rows using exact source values `US-ID`,
  `US-OR`, or `US-WA`.
- The complete MTBS pre-exclusion universe has **187** rows. It has **0** rows
  whose `Incid_Type` is exactly `WF` and **177** whose exact value is
  `Wildfire`.
- No eligibility decision, WFIGS feature snapshot, HLS query, candidate
  selection, imagery access, or denied MTBS field-value access occurred.

## Exact amendment proposed

1. Derive the MTBS state only from the first two `Event_ID` characters and
   require exactly `ID`, `OR`, or `WA`.
2. Require WFIGS `attr_POOState` to equal exactly `US-` plus that MTBS state.
3. Require MTBS `Incid_Type` exactly `Wildfire` and matched WFIGS
   `attr_IncidentTypeCategory` exactly `WF`.
4. Keep canonical candidate values as `ID`/`OR`/`WA` and `Wildfire`.
5. Allow no other alias, prefix removal, name mapping, or fallback. Conflict or
   missing evidence remains unknown and not eligible.

Every substantive design rule remains unchanged: jurisdictions, years, area,
prior exclusions, exact identities, maturity, ecology, HLS metadata, duplicate
handling, capacity, and terminal shortfall behavior.

## Decision consequences

- **Approve:** freeze only these exact representation mappings and resume the
  bounded WFIGS snapshot and M1-U005 enumeration.
- **Reject:** retain the literal predicates. Their observed count is zero, so
  Milestone 1 closes `INCONCLUSIVE` under the frozen 36-slot requirement.
- **Uncertain:** change nothing and retain the gate with your note.

The full evidence is in `E4-EV-0009` and the machine-readable amendment
proposal. Raw source archives and row-level preflight output remain outside
Git under controlled custody/runtime paths.
