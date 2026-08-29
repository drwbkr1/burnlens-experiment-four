# Candidate-universe metadata protocol

## Purpose and boundary

This protocol defines the metadata record, evaluation states, reason codes,
source-representation mappings, and replay behavior for Experiment Four
candidate-universe enumeration. It does not choose an event or authorize
imagery, labels, model artifacts, training, inference, or evaluation. Exact
eligibility values are frozen in `E4-ELIGIBILITY-2026-001`; the only later
amendment is the exact representation mapping frozen in
`E4-M1-LITERAL-ENCODING-AMENDMENT-2026-001`.

## Unit of analysis

One candidate is one whole fire event. A scene, perimeter version, patch,
reference product, model output, or fire complex member is not independently
eligible. Source records that represent the same fire must reconcile to one
canonical event before eligibility.

`schemas/candidate-event.schema.json` contains only source identity, fire,
geography, source-availability, rights, and overlap metadata. Model outputs,
burn indices, predictions, metrics, errors, labels, class balance, and proposed
split roles are prohibited from the candidate record and the decision path.

## Identity and freshness

Identity precedence is:

1. unique fire identifier;
2. source global identifier;
3. source event identifier;
4. project event identifier; and
5. normalized name plus incident year only as a conservative fallback for the
   six Experiment One records that lack one admitted official incident ID.

Any exact prior-event identifier match is permanently excluded. A possible
name-year or spatial match is `unknown`, not fresh, until exact admitted
metadata resolves it. The frozen exclusion manifest is append-only; correcting
an identity creates a successor and never deletes exposure history.

## Evaluation outcomes

The deterministic evaluator uses this precedence:

1. `invalid` for malformed or contradictory records, an unfrozen/invalid
   profile, or an identity conflict;
2. `excluded` when evidence proves any frozen exclusion reason;
3. `unknown` when a required fact is missing, unchecked, or unresolved; and
4. `eligible` only when every frozen requirement passes.

Multiple reasons are retained in the frozen order in the schema-freeze record.
An exclusion does not erase unknowns, and a convenient value may not be
imputed. Input order cannot change a candidate outcome.

## Eligibility profile

`schemas/metadata-eligibility-profile.schema.json` separates the stable
algorithm from owner-approved values. A `proposed` profile must never produce
an eligible candidate. A `frozen` profile requires exact jurisdiction, year,
area, maturity, incident type, perimeter status, ecology, imagery metadata,
reference metadata, rights, prior-exclusion hash, and unknown policy values.

The frozen profile fixes Idaho/Oregon/Washington, 2021-2022, a 1,000-acre
minimum, wildfire-only intent, final maturity, metadata-availability
requirements, admitted rights, prior-event exclusion, duplicate controls, and
unknown-not-eligible under the exact reviewed source package.

## Exact source-representation amendment

The exact owner-approved amendment changes representation only:

1. derive MTBS state only from the first two `Event_ID` characters and require
   exactly `ID`, `OR`, or `WA`;
2. require matched WFIGS `attr_POOState` to equal exactly `US-` plus that MTBS
   state;
3. require MTBS `Incid_Type` exactly `Wildfire` and matched WFIGS
   `attr_IncidentTypeCategory` exactly `WF`; and
4. treat every missing value, non-exact identity, disagreement, or other
   encoding as unknown and not eligible.

No other alias, prefix removal, name mapping, fallback, or normalization is
permitted. Years, areas, prior exclusions, identity, maturity, ecology, HLS
metadata, duplicate handling, capacity, and terminal rules are unchanged. The
original zero-match literal predicates remain retained failure evidence.

## Replay

A replay bundle must bind the candidate schema, frozen eligibility profile,
prior-event exclusion manifest, evaluator source, exact source-row hashes, and
ordered output. The same inputs must reproduce byte-identical candidate IDs,
states, and ordered reason codes. Failed and superseded replays remain visible.

Candidate enumeration requires the frozen profile, admitted source registry,
and exact locked owner responses for source adoption and the representation
amendment. Those gates now pass; every runtime snapshot and replay must remain
hash-bound and outside Git.
