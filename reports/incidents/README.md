# Incident Artifact Reports

PH2 stores local out-of-band incident artifact bundles under:

```text
reports/incidents/{incident_id}/
```

Real incident directories matching `inc-*` are ignored by git because they are
runtime evidence. Commit only templates, samples, and small reviewed guidance
files from this directory.

PH2 does not collect raw logs by default. The `raw/` directory inside generated
bundles is intentionally empty except for a README.
