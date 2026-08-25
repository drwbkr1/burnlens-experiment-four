# BurnLens Experiment Four

BurnLens Experiment Four is a prospective fresh-event burn-change benchmark.
It is designed to address the weak, sparse, retrospective evidence that limited
earlier BurnLens experiments by building a newly selected, whole-event-held-out
Pacific Northwest cohort before model evaluation.

## Current status

Milestone 0 is active from a verified empty public repository under
[issue #1](https://github.com/drwbkr1/burnlens-experiment-four/issues/1).
This repository currently contains control-plane and project-bootstrap
material only. There is no admitted dataset, model, training run, evaluation,
metric, tag, release, deployment, or operational product.

## Research question

> Can fixed burn-change methods generalize across a prospectively selected,
> independently reviewed, whole-event-held-out Pacific Northwest cohort without
> model-assisted event selection, label admission, threshold selection, or
> post-test rescue?

The planned design uses six permanently excluded pilot events and a final
30-event Oregon/Washington/Idaho cohort with 16 training, 6 validation, and 8
sealed test events. HLS v2 L30 and S30 are the proposed imagery backbone. Exact
source adoption, temporal windows, QA rules, reference evidence, masks, and
model protocols remain gated by the milestone sequence.

## Separate outcomes

- `dataset_readiness` records whether the final cohort is fit for the bounded
  scientific use.
- `lifecycle_status` records whether the complete model and evidence lifecycle
  executed and replayed correctly.
- `comparative_status` records the model comparison as `PASS`, `FAIL`,
  `INCONCLUSIVE`, or `INVALID` under frozen rules.
- `release_status` records whether the exact public release was independently
  verified.

A valid negative model result may accompany a successful dataset and lifecycle.
Completion depends on truthful closure, not favorable metrics.

## Claim limits

This project is not official fire information, field-validated ground truth,
independent proof of population-wide accuracy, emergency guidance, or an
operational wildfire product. Reference-source dependence, ambiguity, spatial
registration, temporal coverage, and absent field evidence must remain visible.

## Custody

The canonical checkout is:

```text
C:\Projects\Active\burnlens-experiment-four
```

All data, runtime, cache, temporary, and output custody will remain beneath
`C:\Projects\Active` and outside Git. Prior BurnLens repositories are read-only
provenance sources unless the owner grants a narrow write authorization.

## Project controls

- [Execution goal](docs/governance/EXPERIMENT-FOUR-EXECUTION-GOAL.md)
- [Checkpoint policy](docs/governance/CHECKPOINT-POLICY.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Status](docs/status/STATUS.md)
- [Authority](records/governance/EXPERIMENT-FOUR-AUTHORITY-2026-001.md)
- [Evidence ledger](records/evidence/EVIDENCE-LEDGER.md)
- [Decision register](records/decisions/DECISION-REGISTER.md)

## License and third-party materials

Repository-authored software and documentation are licensed under the MIT
License unless a file states otherwise. That license does not apply to imagery,
reference products, labels, model artifacts, or other third-party material.
