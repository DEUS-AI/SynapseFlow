# Bug Report: Incorrect RediSearch Syntax in FalkorDB Driver v0.27.1

## Summary

`FalkorDriver.build_fulltext_query()` in graphiti-core v0.27.1 generates invalid RediSearch queries when using `group_ids` filtering, causing `RediSearch: Syntax error` failures on FalkorDB.

## Environment

- **graphiti-core version**: 0.27.1
- **FalkorDB version**: latest (falkordb/falkordb:latest)
- **Python version**: 3.13.5
- **Operating system**: macOS (Darwin 25.2.0)

## Bug Description

### Root Cause

The `build_fulltext_query()` method in `graphiti_core/driver/falkordb_driver.py` (lines 346-353) constructs RediSearch queries using **quoted values** for tag field filters:

```python
escaped_group_ids = [f'"{gid}"' for gid in group_ids]
group_values = '|'.join(escaped_group_ids)
group_filter = f'(@group_id:{group_values})'
```

This generates queries like:
```
(@group_id:"patient-demo") (Hello | Matucha | good | morning)
```

### The Problem

RediSearch **does not accept quoted values** with the `@field:` syntax for tag fields. The `@` prefix is for field/tag queries, and values must be either:
- **Unescaped** (if no special characters): `@group_id:simple`
- **In curly braces** (for tags with special chars): `@group_id:{patient-demo}`

The current implementation using quotes `@group_id:"value"` is **invalid RediSearch syntax** and causes parse errors.

### Error Message

```
redis.exceptions.ResponseError: RediSearch: Syntax error at offset 19 near patient
```

Where offset 19 points to the character after `@group_id:"` in the query string.

## Steps to Reproduce

1. Install graphiti-core v0.27.1 with FalkorDB:
   ```bash
   pip install graphiti-core[falkordb]==0.27.1
   ```

2. Set up a FalkorDB instance:
   ```bash
   docker run -p 6379:6379 falkordb/falkordb:latest
   ```

3. Create a simple test script:
   ```python
   from graphiti_core import Graphiti
   from graphiti_core.driver.falkordb_driver import FalkorDriver
   from graphiti_core.search.search import search
   from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER
   from graphiti_core.search.search_filters import SearchFilters
   import asyncio

   async def test_search():
       driver = FalkorDriver(host='localhost', port=6379)
       graphiti = Graphiti(graph_driver=driver)
       await graphiti.build_indices_and_constraints()

       # Add a test episode
       await graphiti.add_episode(
           name="Test Episode",
           episode_body="Hello world test message",
           source_description="Test",
           reference_time=None,
           group_id="patient-demo"
       )

       # Search with group_ids - THIS WILL FAIL
       results = await search(
           clients=graphiti.clients,
           query="Hello world",
           group_ids=["patient-demo"],
           config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
           search_filter=SearchFilters(),
       )

       await graphiti.close()

   asyncio.run(test_search())
   ```

4. Run the script:
   ```bash
   python test_script.py
   ```

5. **Expected behavior**: Search returns results filtered by `group_id`
6. **Actual behavior**: Crashes with `RediSearch: Syntax error at offset 19 near patient`

## Detailed Analysis

### Current Implementation (BROKEN)

Location: `graphiti_core/driver/falkordb_driver.py:346-353`

```python
if group_ids is None or len(group_ids) == 0:
    group_filter = ''
else:
    # Escape group_ids with quotes to prevent RediSearch syntax errors
    # with reserved words like "main" or special characters like hyphens
    escaped_group_ids = [f'"{gid}"' for gid in group_ids]
    group_values = '|'.join(escaped_group_ids)
    group_filter = f'(@group_id:{group_values})'
```

**Generated query** (INVALID):
```
(@group_id:"patient-demo") (search | terms)
```

### Correct RediSearch Syntax

RediSearch tag field syntax requires **curly braces** for values with special characters:

```python
if group_ids is None or len(group_ids) == 0:
    group_filter = ''
else:
    # Use curly braces for tag fields (correct RediSearch syntax)
    group_values = '|'.join(group_ids)
    group_filter = f'@group_id:{{{group_values}}}'  # Note: double {{ for f-string escaping
```

**Generated query** (VALID):
```
@group_id:{patient-demo} (search | terms)
```

### Why This Matters

1. **Hyphens are common** in group_ids (e.g., UUIDs, patient IDs)
2. **Quotes don't escape hyphens** in RediSearch tag syntax
3. **Curly braces tell RediSearch** to treat the entire value as a single tag

## RediSearch Documentation Reference

From [RediSearch Query Syntax](https://redis.io/docs/stack/search/reference/query_syntax/):

> **Tag Fields**: To query a tag field, use the syntax `@field:{value}`. The curly braces indicate that the value should be treated as a tag.
>
> For multiple tags: `@field:{value1|value2|value3}`

Quotes (`"value"`) are for **phrase matching in text fields**, not for tag fields.

## Proposed Fix

Replace lines 346-353 in `graphiti_core/driver/falkordb_driver.py`:

```python
if group_ids is None or len(group_ids) == 0:
    group_filter = ''
else:
    # Use curly braces for tag fields (correct RediSearch syntax)
    # Values inside {} are treated as tags - no additional escaping needed
    group_values = '|'.join(group_ids)
    group_filter = f'@group_id:{{{group_values}}}'
```

## Workaround (Temporary Fix)

Users can monkey-patch the method until a fix is released:

```python
from graphiti_core.driver.falkordb_driver import FalkorDriver, STOPWORDS

def _fixed_build_fulltext_query(
    self, query: str, group_ids: list[str] | None = None, max_query_length: int = 128
) -> str:
    """Fixed version using correct RediSearch tag syntax."""
    if group_ids is None or len(group_ids) == 0:
        group_filter = ''
    else:
        group_values = '|'.join(group_ids)
        group_filter = f'@group_id:{{{group_values}}}'

    sanitized_query = self.sanitize(query)
    query_words = sanitized_query.split()
    filtered_words = [word for word in query_words if word and word.lower() not in STOPWORDS]
    sanitized_query = ' | '.join(filtered_words)

    if len(sanitized_query.split(' ')) + len(group_ids or '') >= max_query_length:
        return ''

    if group_filter and sanitized_query:
        return f'{group_filter} ({sanitized_query})'
    elif group_filter:
        return group_filter
    else:
        return f'({sanitized_query})'

# Apply monkey-patch
FalkorDriver.build_fulltext_query = _fixed_build_fulltext_query
```

## Impact

- **Severity**: High
- **Affected users**: Anyone using FalkorDB backend with `group_ids` filtering
- **Workaround available**: Yes (monkey-patch)
- **Data loss risk**: None (query-only issue)

## Version History

- **v0.17.6**: Used Lucene syntax `group_id:"value"` (also broken)
- **v0.27.0**: Attempted fix using quotes `(@group_id:"value")` (still broken)
- **v0.27.1**: No change from v0.27.0 (still broken)
- **Required fix**: Use curly braces `@group_id:{value}`

## Additional Context

The comment in the code (line 349-350) mentions:
> "Escape group_ids with quotes to prevent RediSearch syntax errors with reserved words like "main" or special characters like hyphens"

This reasoning is **incorrect** for RediSearch. Curly braces `{}` are the proper way to handle reserved words and special characters in tag fields, not quotes.

## Test Cases

### Test 1: Simple group_id with hyphens
```python
assert driver.build_fulltext_query("hello", ["patient-demo"]) == "@group_id:{patient-demo} (hello)"
```

### Test 2: Multiple group_ids
```python
assert driver.build_fulltext_query("hello", ["id-1", "id-2"]) == "@group_id:{id-1|id-2} (hello)"
```

### Test 3: UUID-style group_id
```python
uuid_id = "session-a9668157-4080-4ffb-9770-0932abf20845"
assert driver.build_fulltext_query("test", [uuid_id]) == f"@group_id:{{{uuid_id}}} (test)"
```

### Test 4: Reserved words
```python
assert driver.build_fulltext_query("search", ["main"]) == "@group_id:{main} (search)"
```

## Related Issues

- Possibly related to the v0.27.0 changelog entry: "Sanitization of special characters in fulltext queries and escaping of group_ids"
- This was an attempted fix but used incorrect RediSearch syntax

## References

- [RediSearch Query Syntax Documentation](https://redis.io/docs/stack/search/reference/query_syntax/)
- [RediSearch Tag Fields](https://redis.io/docs/stack/search/reference/tags/)
- [FalkorDB Documentation](https://docs.falkordb.com/)
