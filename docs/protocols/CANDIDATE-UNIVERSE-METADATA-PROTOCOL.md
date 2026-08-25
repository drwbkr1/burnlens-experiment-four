# Candidate-universe metadata protocol

## Purpose and boundary

This protocol defines the metadata record, evaluation states, reason codes,
and replay behavior before any Experiment Four candidate row is observed. It
does not admit an external source, authorize source-body access, or choose an
event. The exact year, size, maturity, ecology, and source-specific duplicate
values remain an explicit owner decision because the approved charter names
those dimensions but does not supply their numeric or categorical values.

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

The current proposal fixes only what the owner already approved or what is a
fail-closed control: Idaho/Oregon/Washington, wildfire-only intent,
metadata-availability requirements, admitted rights, prior-event exclusion,
and unknown-not-eligible. Numeric ranges, exact vocabularies, source revisions,
and duplicate tie-breaks are pending the hash-bound owner gate.

## Replay

A replay bundle must bind the candidate schema, frozen eligibility profile,
prior-event exclusion manifest, evaluator source, exact source-row hashes, and
ordered output. The same inputs must reproduce byte-identical candidate IDs,
states, and ordered reason codes. Failed and superseded replays remain visible.

No candidate enumeration may begin until the profile status is `frozen`, its
exact owner response is locked, and every admitted source gate passes.
