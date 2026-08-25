# 2026-08-25 — Source review checkpoint

Milestone 1 now has an exact pre-adoption source package for NIFC WFIGS, USGS
MTBS v12, NASA HLSL30 v2.0, NASA HLSS30 v2.0, and EPA Level III ecoregions.
The proposal fixes the 2021–2022 Idaho, Oregon, and Washington universe, a
1,000-acre minimum in both MTBS and WFIGS, exact identifier matching, broad
ecology and HLS metadata availability rules, duplicate handling, and a
terminal `INCONCLUSIVE` shortfall rule before any candidate rows are seen.

The package is bound by review-bundle SHA-256
`7423219b7d23388546fb7d1db0d66e83ade8958fe20ee97fc19ab95952ba62f7`.
Its desktop and narrow rendered states start blank, block incomplete export,
require attestation, and export a hash-named response. The automated round
trip used an all-`a` fixture hash and created zero human decisions.

The first source-review validation attempt failed because the validator used
literal wording for four equivalent prohibited concepts and interpreted every
JavaScript `checked` token as a preselected decision. The validator was
narrowly repaired to inspect accepted semantic phrases and the actual radio
attribute. It then passed, as did all 17 tests.

No source was adopted, no candidate row was inspected, and no scientific
source body was opened. The package remains at the exact owner gate.
