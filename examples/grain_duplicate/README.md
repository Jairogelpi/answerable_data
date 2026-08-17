# Golden example: duplicate unit of analysis

This case looks like a normal campaign-retention comparison, but `customer_id=c08` appears twice. The declared grain is one row per customer, so the analytical input is not trustworthy at the requested unit of analysis.

Run it:

```bash
answerable assess \
  --data examples/grain_duplicate/customers.csv \
  --question examples/grain_duplicate/question.yaml \
  --output runs/grain_duplicate
```

The important signal is `duplicate_entities`. Answerable must not strengthen the conclusion while the unit-of-analysis invariant is broken.
