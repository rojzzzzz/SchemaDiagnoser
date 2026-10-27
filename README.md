# SchemaDiagnoser

SchemaDiagnoser is a package that contains the 'check_schema' function, a schema diagnostics tool with an optional but recommended AI review parameter powered by [Jev AI](https://typesafe.ai/blog/introducing-system-one-models-and-jev). A deterministic python script looks for changes between the received schema and the declared from the contract, if the 'ai_review' parameter in selected, Jev supplies a likely explanation and suggested checks


```python
from SchemaDiagnoser.fn import check_schema

report = check_schema(
    {"id": int, "amount": float},
    [{"id": 1, "amount": "19.99"}],
    ai_review=True,
)
```

Local checks use the standard library. Install `typesafe-sdk` and set
`TYPESAFE_API_KEY` (or pass `api_key=`) for AI review.

## Latency

SchemaDiagnoser is primarly thought for Event-Driven or pipelines moving data in real time, that makes controlling latency gains one of the most important benchmarks. The following are estimations based on the Jev AI documentation, a time per call is provided for each possible scenrio:


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

## How to use it

Import `check_schema` and pass the expected contract and either records or an
incoming schema. The remaining parameters are keyword-only.

```python
from SchemaDiagnoser.fn import check_schema

contract = {"id": int, "amount": float, "note": "str|null"}
records = [{"id": 1, "amount": "19.99", "note": None}]

report = check_schema(contract, records)
print(report["valid"])    # False: amount is a string, not a float
print(report["changes"])  # Details of the mismatch
```

| Parameter | Expected value | Default and behavior |
| --- | --- | --- |
| `schema_contract` | A nonempty schema: a field-to-type dictionary, a list of `(field, type)` pairs, a `schema` or `contract` wrapper, or parallel `columns` and `types` (or `dtypes`) lists. | Required. Field names must be nonempty strings and unique. |
| `incoming` | A dictionary describing the incoming schema, or a nonempty list of record dictionaries. | Required. Wrap a single record in a list; a bare dictionary is interpreted as schema metadata. |
| `ai_review` | Boolean. | `False`. When `True`, request a Jev review only if changes are found. Install `typesafe-sdk` and configure an API key first. |
| `allow_extra` | Boolean. | `False`. When `True`, added fields are reported as nonblocking changes. |
| `context` | A string, JSON-serializable dictionary, or `None`. | `None`. Additional context sent to Jev with schema metadata; include only information appropriate to send to the API. |
| `api_key` | A TypeSafe API key string or `None`. | `None`. Falls back to the `TYPESAFE_API_KEY` environment variable. |
| `timeout` | A number of seconds. | `1.0`. Bounds HTTP operations, not the total wall-clock time. Automatic retries are disabled. |
| `cache` | Boolean. | `True`. Reuses equivalent successful reviews for up to five minutes per process; `False` requests a fresh review. |

Types can be Python types, such as `int` and `str`, or type names, such as
`"integer"` and `"string"`. Explicit unions such as `int | float`,
`"int|float"`, and `"str|null"` allow multiple types. Every contract field is
required: allowing null does not allow the field to be missing. Types are not
coerced; for example, an integer does not satisfy a `float` contract. Nested
lists and dictionaries are checked only by their container type.

To compare schemas instead of records, pass type declarations in `incoming`:

```python
report = check_schema(
    {"columns": ["id", "amount"], "types": ["integer", "float"]},
    {"id": "integer", "amount": "string"},
    ai_review=True,
    context="Order amounts should be numeric.",
)
```

The returned dictionary contains `valid`, `changes`, and `review`. `valid` is
determined by local checks; Jev cannot override it. `changes` describes each
affected field, its issues, expected and received types, whether it blocks
validation, and available evidence. `review["status"]` is `disabled`,
`not_needed`, `completed`, or `failed`. A completed review includes a
diagnosis and may include rename hypotheses or partial-coverage details. A
failed review includes an error and leaves the local validation result intact.
Malformed inputs, an empty contract, and an empty record batch raise an error.

