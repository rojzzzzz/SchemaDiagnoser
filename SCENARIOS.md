# Schema diagnosis and pipeline handling

These tables cover the supported decision branches, not every possible business
rule. When findings coexist, **any blocking finding makes the record/batch
invalid**. Jev cannot override this. Invalid data does not terminate the example
consumer: it is reported, alerted, and excluded from adaptation; the loop then
continues. Invalid API inputs or contract configuration still raise errors.

## Contract and data scenarios

| Scenario | `check_schema` | Example handling |
| --- | --- | --- |
| All fields present with permitted types | `valid=True`, no changes | Continue unchanged; no AI or alert |
| Type aliases or union ordering differ | Canonicalized; no drift | Continue unchanged |
| Different rows use different explicitly allowed types | Valid | Continue without conversion |
| Null permitted by a union or null-only declaration | Valid, whether some or all rows are null | Continue; no filling or alert solely for nulls |
| Null not permitted | Blocking `null_values` | Alert; reject this order; consumer continues |
| Required field absent everywhere | Blocking `missing` | Alert; reject this order; consumer continues |
| Required field absent in some rows | Blocking `missing_in_rows` | Invalid batch; no defaults invented |
| Nullable field absent | Still blocking `missing` / `missing_in_rows` | Reject; nullable does not allow omission |
| Type outside the declared set | Blocking `type_changed` | Reject; no implicit cast |
| Incoming required metadata type is `unknown` / `mixed` | Blocking `unknown_type` | Reject; compatibility cannot be established |
| Added field, `allow_extra=False` | Blocking `added` | Invalid |
| Added field, `allow_extra=True` | Nonblocking `added`, regardless of its value type | Alert; accepted; eligible for limited adaptation |
| Required name replaced by another name | Missing original plus added replacement | Reject; a rename hypothesis does not approve a repair |
| Canonical name and extra spelling variant both present | Extra-field policy applies | Deduplicate only under the conditions below |
| Several independent issues | All field findings retained; any blocker wins | Reject if any required constraint fails |
| Dictionary/list contents, ranges, finiteness, units, or meaning change without a checked type change | Not inspected by this flat schema checker | No claim of business-value validity |

Every field is required. Permitted types are explicit: `int | float` accepts both,
while `float` alone rejects an integer. `bool` is distinct from `int`. `str | None`
accepts strings and nulls; it still rejects a missing field. No casting occurs.
String equivalents (`"int|float"`, `"str|null"`) work in YAML/JSON. `None`,
`type(None)`, `"null"`, and `"NoneType"` declare a null-only field.

For schema metadata, the incoming type set must be a subset of the expected type
set. For records, the observed set includes all actual types and nulls. Therefore
batch validity equals the validity of all constituent records. Findings are
grouped per field; counts and bounded row examples explain observed violations.

## Input and configuration scenarios

| Scenario | Handling |
| --- | --- |
| Plain name/type mapping, `(name, type)` pairs, `schema`/`contract` wrapper | Normalize to the same schema |
| Parallel `columns` with `types` or `dtypes` lists | Normalize after checking lengths and duplicates |
| Python type/union, `typing.Optional`/`Union`, or type-name/union string | Normalize aliases and explicit member types |
| Column named `schema`, `contract`, `columns`, `types`, or `dtypes` | Valid; wrapper detection considers value shape |
| Bare dictionary supplied as `incoming` | Always schema metadata; use `[event]` for record values |
| Empty incoming schema `{}` or empty record `[{}]` | Missing-field findings, not an exception |
| Empty incoming `columns` plus empty type list | Same as an empty incoming schema |
| Empty contract or empty record batch | `ValueError` |
| Duplicate column pairs, blank/non-string names, malformed pairs, mismatched list lengths | Input error (`ValueError` / `TypeError`) |
| Both schema wrappers, or both `types` and `dtypes` in a parallel-list wrapper | `ValueError`; no silent precedence |
| Invalid dtype or empty union member, e.g. `"int|"` | `TypeError` |
| Contract declares `unknown` / `mixed`, alone or in a union | `ValueError` |
| Incoming value is neither schema dict nor record list; list contains non-dicts | `TypeError` |
| Parameterized nested type such as `list[int]` | Unsupported; use `list` for a container check |

Errors here indicate malformed function input or unusable configuration. They
are distinct from an ordinary out-of-contract record represented by `valid=False`.

## AI and cache scenarios

| Scenario | Handling |
| --- | --- |
| `ai_review=False` | `disabled`; local facts still returned |
| AI enabled, no drift | `not_needed`; no SDK import or network request |
| Successful fresh review | `completed`; diagnosis, scores, next check, optional rename hypotheses |
| Equivalent cached review | `completed`, `cached=True`, zero new input tokens; rows still validated |
| Cache bypass, changed contract/types/evidence/context/settings, expiration, or eviction | Fresh review requested |
| Missing SDK/credentials, timeout, API failure, or invalid choices/scores | `failed` with error; local result unchanged; no automatic retry or failure caching |
| More than 32 detailed changes, 16 rename questions, or 32 rename candidates | Local findings remain complete; AI `coverage` discloses truncated dimensions |
| Multiple missing fields select the same replacement | `competing_changes` discloses ambiguity; no acceptance override |

The review cache is bounded to 256 entries for five minutes per process. It does
not cache validation results or row positions. Returned reviews cannot mutate
cached entries. Concurrent first requests may duplicate AI work. A timeout
limits HTTP operations rather than guaranteeing a total wall-clock deadline.

## Every Jev category and adaptation

Adaptation requires a completed review, no partial coverage, and selected
probability at least 0.9. It operates only on the **same unchanged accepted
order/report pair**, without repeating validation or making another AI call.

| Jev category | Adaptation |
| --- | --- |
| `schema_expansion` | Remove only fields reported as added; preserve the original order |
| `naming_change` | Remove only unique case/underscore aliases with identical scalar type/value |
| `mixed_changes` | Same verified alias cleanup; keep other extras |
| `representation_change` | No casting |
| `semantic_change` | No unit or meaning conversion |
| `event_shape_change` | No routing or schema-version conversion |
| `inconsistent_records` | No filling, dropping rows, or guessed normalization |
| `incomplete_payload` | No invented values |
| `unknown` | No changes |

Low probability, partial/failed/disabled review, or no review leaves the copy
unchanged. An alias with a different type/value, multiple canonical matches,
or nested values is retained. Identical null aliases can be removed when the
canonical null was explicitly permitted. Required fields are never changed.
True renames with a missing required name cannot reach adaptation.

## Alerts and consumer behavior

| Scenario | Handling |
| --- | --- |
| Clean record, including permitted nulls and alternate types | No alert; continue |
| Accepted extra fields | Advisory email attempt; then eligible for adaptation |
| Rejected schema record | Rejection email attempt; skip adaptation and continue the loop |
| Jev fails on a changed record | Include AI error in the alert; local acceptance still controls the record |
| SMTP connection, authentication, or delivery fails | Log failure; keep the validation result; continue |
| SMTP port 465 | Verified implicit TLS; authenticate if `SMTP_PASSWORD` is configured |
| Other SMTP port with configured password | Verified STARTTLS before authentication |
| Other SMTP port without a password | Plain SMTP relay connection; no credentials sent |
| Repeated changed records | One email attempt per call; no cooldown or delivery queue |

This remains a mock validation/adaptation consumer. It does not publish results,
commit Kafka offsets, or implement durable quarantine. Rejected records are not
passed downstream; output delivery, acknowledgement, and replay policies remain
application work. No tests send actual emails or contact Jev.
