# Isolation test report — Block 2

Status: **PASS**

The synthetic suite proves two client scopes plus global scope. It verifies that client A cannot retrieve client B by pointer, SQL search, Graphify target, or evidence identity; missing, unresolved, conflicting, and disabled scopes fail before access; global notes require the declared global rule; traversal, `_backups/`, symlink escape, denied pointers, and excluded paths remain unavailable.

Instrumented openers, deserializers, Graphify candidate loaders, and search selection assertions prove forbidden sources were not opened or materialized. Search applies `client_scope = ?` in SQL before rows/snippets are constructed. Graphify returns path/score only after namespace and target validation. Evidence fixtures validate identity before calling their supplied loader.

Pre-write gate: the 36-test isolation/loader/classification/promotion/Block-1 set passed before the real vault mutation was attempted.

Relevant automated files: `tests/test_business_brain_scope.py`, `tests/test_business_brain_search_scope.py`, `tests/test_business_brain_context.py`, `tests/test_business_brain_graph.py`, and `tests/business_brain_test_support.py`.

Token usage: no agent invocation
