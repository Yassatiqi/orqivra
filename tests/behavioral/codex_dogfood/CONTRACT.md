# JSONL parser contract

`parse_jsonl(text)` accepts a string containing newline-delimited JSON records and returns a list of JSON objects in input order. Empty lines and lines containing only whitespace are ignored. Malformed JSON and valid JSON values that are not objects raise `ValueError` with the one-based source line number. An empty input returns an empty list.

The helper is a controlled behavioral fixture for the Codex edition dogfood trial. It does not change the ORQIVRA CLI contract.
