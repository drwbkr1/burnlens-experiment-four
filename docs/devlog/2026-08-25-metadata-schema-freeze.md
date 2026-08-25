# 2026-08-25 — Metadata schema freeze

The candidate-event schema, eligibility-profile schema, deterministic
evaluator, ordered reason codes, identity precedence, unknown semantics, and
replay binding were created before observing any Experiment Four candidate
row. Model outputs, indices, predictions, metrics, labels, errors, and split
roles are prohibited from candidate records and decision logic.

The approved goal fixes the three states and the dimensions that must govern
eligibility, but it does not fix numeric year, area, or maturity values or the
exact ecology and duplicate rules. Those values remain visibly `proposed` and
must be bound with exact sources in the owner review bundle. The evaluator
returns `invalid` for an unfrozen profile, so candidate enumeration cannot
silently proceed.

The first validation attempt found that the bootstrap-era repository allowlist
did not include the `schemas/` and `src/` paths authorized by Milestone 1. The
allowlist was narrowly repaired. All schema controls and 14 tests then passed.
No external source was adopted and no scientific source body was opened.
