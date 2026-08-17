# Campaign retention — golden case

A marketing team asks whether a campaign increased 90-day retention. The observed
difference is real; the causal conclusion is not defensible.

```bash
answerable assess \
  --data examples/campaign_retention/customers.csv \
  --question examples/campaign_retention/question.yaml \
  --output runs/campaign_retention
```

## The data

50 customers acquired between 2025-01-09 and 2025-05-30, one row per customer.

| Group | Customers | 90-day retention |
| --- | --- | --- |
| exposed (`campaign_exposed = true`) | 25 | 60.0% |
| unexposed (`campaign_exposed = false`) | 25 | 48.0% |

A naive reading reports a 12-point lift and attributes it to the campaign.

## The traps

1. **No overlap (positivity violation).** Every exposed customer arrived through the
   `paid` channel and every unexposed customer through `organic`. No covariate stratum
   contains both groups, so adjustment cannot remove the channel confound.
2. **Immature cohorts.** Customers acquired after 2025-04-01 have not completed the
   90-day observation window by the 2025-06-30 analysis cutoff, so their retention is
   understated.

## The verdict

```text
FUNDAMENTALLY_UNIDENTIFIABLE
```

Allowed: *"Observed 90-day retention was 12 points higher among exposed customers."*

Forbidden: *"The campaign caused a 12 point increase in 90-day retention."* and
*"The campaign led to higher retention."*

Minimal repair: exposed and unexposed customers inside the same covariate stratum —
a randomized holdout, or exposure that varies within each channel.

## Reproducibility

The same inputs always produce the same assessment id and warrant content hash.
Changing one row changes both, and editing `warrant.json` makes
`answerable warrant verify` exit with code `3`.
