# v0.4 Aggregation and Profile Smoothing

## From scored events to scene scores

`v04_scored_events.jsonl` is the scored event-level output from the v0.4 scoring pipeline. The aggregation layer groups events by `session_id`, `user_id`, `scene_id`, and `task_id`, then produces one scene row per group.

Only trustworthy, production-like rows participate in the score calculation:

- `scored=true`
- `is_valid_event=true`
- `confidence >= 0.2`
- `is_demo` is not true
- `is_low_quality` is not true and `low_quality` is not present in quality flags

For each scene, the five personality dimensions are calculated with confidence-weighted averaging:

```text
weighted_score = sum(score_i * confidence_i) / sum(confidence_i)
```

Evidence is carried forward from participating events, deduplicated, and capped at 10 entries per scene. If a scene has no participating events, all five scene score fields are `null` and `aggregation_status` is `no_valid_events`.

## From scene to session scores

Session aggregation uses the same event-level inclusion rules and the same confidence-weighted formula, grouped by `session_id` and `user_id`. The session row includes total input events, participating events, skipped events, scene count, session confidence, deduplicated evidence, and `aggregation_status`.

This keeps the session score directly traceable to event evidence while still allowing scene scores to be inspected independently.

## Why low-confidence events are excluded

Events with `confidence < 0.2` are too uncertain to safely influence a user profile. Keeping them out of aggregation reduces noise and prevents weak signals from accumulating into persistent personality changes.

## Why invalid, low-quality, and demo events are excluded

Invalid and low-quality events can contain empty answers, copied prompts, malformed rows, or otherwise unreliable behavior. Demo events may be synthetic or non-user data. Excluding these rows keeps the profile update tied to valid user responses only.

## Profile smoothing

The profile update starts from an old profile and moves partway toward the current session score:

```text
new_profile = (1 - alpha) * old_profile + alpha * session_score
```

The default `alpha` is `0.2`, so a single session can update the profile without overwriting prior history. If a session score dimension is `null`, that dimension keeps the previous profile value.

## Why the initial profile is 50

The five dimensions use a 0-100 scale. Starting at 50 is a neutral midpoint, so the first valid sessions can move the profile upward or downward without assuming a prior personality tendency.

## Future `/score/session` mapping

The generated `v04_session_scores.jsonl` is the natural payload shape for a future `/score/session` endpoint: it contains `session_id`, `user_id`, `session_score`, `session_confidence`, evidence, event counts, and aggregation status. The endpoint can return this session row directly and optionally include the corresponding profile update.

## Mapping to 《熊心壮职》 pages

- Page 11: 日终阶段性 `session_report` can use `v04_session_scores` for backend state, while the frontend does not display personality.
- Page 12: The final `session_report` trigger can consume the same session aggregation after enough valid events exist.
- Page 14: The final personality report can display the smoothed `updated_profile` from `v04_profile_updates`.
- Page 16: The archived profile can store `updated_profile` for cross-round inheritance.
