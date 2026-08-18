# Warning Transitions

Warning transitions are primary, deterministic events derived from adjacent persisted snapshots for
the same ticker. They complement the warning-history timeline; an unchanged snapshot does not create
an event.

## Transition semantics

| Type                | Meaning                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------- |
| `new_watch`         | First actionable watch state, or a move from no-alert to watch.                               |
| `new_alert`         | First high-risk alert state for a ticker.                                                     |
| `upgraded`          | A non-alert state moves to alert.                                                             |
| `downgraded`        | Alert moves down to watch.                                                                    |
| `resolved`          | Alert or watch moves to no-alert.                                                             |
| `persistent_alert`  | A changed snapshot remains alert. Identical snapshots are ignored.                            |
| `low_trust_warning` | The current state is abstain/low-trust, including high uncertainty or calibration abstention. |

The detector sorts a batch by ticker and emits at most one primary event per current snapshot.
Low-trust takes precedence over a generic upgrade so clients do not mistake a non-actionable output
for a confident alert.

## Persistence and serving

Migration `infra/postgres/init/006_warning_transitions.sql` stores the previous and current levels,
run/batch IDs, detection time, and a unique `deduplication_key`. The Python prediction writer
compares the latest prior warning record before inserting a transition with
`ON CONFLICT DO NOTHING`.

Clients can read the newest events through:

```text
GET /api/v1/analysis/{ticker}/transitions?limit=90
```

The response is `warning_transition.v1`; it is a timeline of model state changes, not investment
advice or an automated trading signal.
