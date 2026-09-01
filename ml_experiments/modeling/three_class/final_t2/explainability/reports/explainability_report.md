# Frozen final T2 post-hoc explainability report

The frozen pipeline was loaded without fitting. Its SHA-256 matches the final manifest. Test contains 948 unique labeled events and predictions reproduce the frozen output. No Maturity data was used.

## Global importance

- Grouped impurity top 3: magnitude_group_unknown, disaster_type, disaster_subtype.
- Test permutation top 3 by Macro-F1 decrease: magnitude_group_unknown, disaster_type, disaster_subtype.
- Class-balanced grouped SHAP top 3: magnitude_group_unknown, disaster_type, disaster_subtype.

Impurity importance sums split-gain allocations and may favor high-cardinality fields. Permutation importance measures performance change on this finite Test set and can be negative. SHAP describes how the frozen model distributes output around its baseline; it is not causal evidence.

## SHAP audit

TreeExplainer 0.52.0 was applied to 312 fixed, class-balanced Test events using the already-fitted preprocessor. Class counts are {'Low': 104, 'Moderate': 104, 'Severe': 104}. Equal class counts prevent the larger Moderate class from dominating the summary. Therefore, “global SHAP” here means class-balanced grouped mean absolute SHAP and is not the Test-prevalence-weighted global importance for all 948 events. Output shape was checked as sample × 331 transformed features × 3 classes; additive reconstruction maximum error was 6e-15.

## Cases and errors

Twelve cases selected by the archived stable rules cover three correct groups and Severe→Low, Moderate→Low, Low→Severe. Test contains 31 Severe→Low, 147 Moderate→Low and 14 Low→Severe events. Severe→Low errors with predicted Low output probability ≥0.70: 7. Probabilities were not calibrated and indicate relative model output strength, not reliable calibrated confidence.

Interpretations are model-behavior descriptions only. A large local contribution means that a feature affected this fitted model's output for the event; it does not mean the feature caused real-world mortality.
