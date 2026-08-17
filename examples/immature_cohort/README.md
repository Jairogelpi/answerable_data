# Golden example: immature cohort

This case has overlap between exposed and unexposed customers, but two recent customers have not completed the required 90-day observation window at the analysis cutoff.

Run it:

```bash
answerable assess \
  --data examples/immature_cohort/customers.csv \
  --question examples/immature_cohort/question.yaml \
  --output runs/immature_cohort
```

The important signal is `immature_cohort`. A valid design can still be unanswerable *yet* when the outcome window is incomplete.
