# SchemaDiagnoser

Schema diagnostics tool with an optional that uses !(Jev AI)[https://typesafe.ai/blog/introducing-system-one-models-and-jev]  for an optional but recommended  review. A deterministic python scripts looks for changes between the received schema and the declared from the contract, if the ai_review paramater is selected, Jev supplies a likely explanation and suggested checks.



```python
from SchemaDiagnoser import check_schema

report = check_schema(
    {"id": int, "amount": float},
    [{"id": 1, "amount": "19.99"}],
    ai_review=True,
)
```

Local checks use the standard library. Install `typesafe-sdk` and set
`TYPESAFE_API_KEY` (or pass `api_key=`) for AI review. The example validator also
accepts the `API_KEY` configured in `use_example/config.py`.

## Latency


| Case | Time per call |
| --- | ---: |
| Clean record, AI disabled | 21.3 µs |
| Clean record, AI enabled | 21.6 µs |
| Schema drift, AI disabled | 33.5 µs |
| Schema drift, cached AI review | 73.9 µs |
| Schema drift, fresh review with immediate mock | 55.9 µs |


## AI review cost

As of October 2026, [TypeSafe lists Jev](https://docs.typesafe.ai/models) at
**$0.042 per million input tokens**, with free output tokens. The cost of
`N` fresh requests is:

```text
N × average input tokens per request × $0.042 / 1,000,000
```

For planning, the table assumes 400–1,000 input tokens per request. That is a
rough estimate, not a measured Jev token count: request size depends on the
changes, context, and rename questions. The function sends schema metadata and
context, not record values. Successful fresh reviews return the actual count in
`report["review"]["input_tokens"]`; use that value to calculate actual costs.

| Fresh API requests | Estimated cost |
| ---: | ---: |
| 1 | $0.0000168–$0.000042 |
| 1,000 | $0.0168–$0.042 |
| 10,000 | $0.168–$0.42 |
| 100,000 | $1.68–$4.20 |
| 1,000,000 | $16.80–$42.00 |

These are Jev input charges only. Clean records and cache hits incur no Jev
request charge; the number of fresh requests depends on the drift patterns and
cache behavior.


