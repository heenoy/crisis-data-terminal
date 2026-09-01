# Case selection rules

## Fixed groups and quota

Six groups are defined before inspection: correct Low, correct Moderate, correct Severe, Severe→Low, Moderate→Low, and Low→Severe. The quota is two events per group. If a group contains fewer than two candidates, all available candidates are retained and the quota is not borrowed from another group.

## Completeness score and ordering

The completeness score is the count of non-missing values among exactly three fields: `hdi`, `event_month`, and `magnitude_robust_z`. Each non-missing field contributes one point, so the score ranges from 0 to 3. Within each group, candidates are stably sorted by: (1) probability assigned to the predicted class, descending; (2) completeness score, descending; and (3) `event_id`, ascending. Thus all remaining ties are resolved by `event_id`.

## Diversity pass and fallback

Two global sets, used country codes and used disaster types, are maintained across groups in the fixed group order above. On the first pass through a group's sorted candidates, an event is selected only when both its `country_code` and `disaster_type` have not appeared in any previously selected event. Candidates failing either condition are skipped during this pass. Each selected event immediately adds its country code and disaster type to the global sets.

If fewer than two events have been selected after the diversity pass, a second pass traverses the same sorted candidate list and selects the earliest not-yet-selected events without applying country or disaster-type restrictions until the quota is filled or candidates are exhausted. No manual case substitution is permitted.
