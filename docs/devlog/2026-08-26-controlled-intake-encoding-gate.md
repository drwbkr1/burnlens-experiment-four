# 2026-08-26 — Controlled intake and literal-encoding gate

M1-U005 acquired the exact approved MTBS v12 perimeter and EPA Level III
ecoregion archives through separate staging and custody roots. Both transfers
used exclusive staging files, deterministic ZIP and shapefile checks, computed
SHA-256, and destination-directory hard-link promotion that fails if the final
path exists. The promoted archives are read-only and the controlled-intake
validator rehashes both live custody files successfully.

One failed MTBS preflight is retained. The locator copied from the source-gate
evidence resolved to the 31,562-byte metadata XML, not the approved archive.
No body was downloaded. The exact ZIP locator was then resolved from the same
approved ScienceBase item and matched file name, media type, 374,092,911-byte
size, and publisher MD5 before acquisition.

The dependency-free MTBS reader opened only the reviewed allowlist. It accounts
for 187 pre-exclusion 2021–2022 Idaho/Oregon/Washington rows and no duplicate
Event_ID or non-null IRWIN-ID groups. Denied MTBS field names are present in the
schema, but their row values were not opened. No eligibility decision exists.

Enumeration stopped before the WFIGS feature snapshot because the frozen
literal predicates conflict with the admitted source encodings. WFIGS has zero
unprefixed `ID`/`OR`/`WA` rows and 1,756 exact `US-ID`/`US-OR`/`US-WA` rows in
the approved window. MTBS has zero target-universe rows with type `WF` and 177
with exact type `Wildfire`. An exact representation-only amendment is prepared
at bundle SHA-256
`3ff69ce031313db2010706cf481a63c24d45a88cfb23c2f6bb7a38d96f7b972a`.
No normalization is implicit.
