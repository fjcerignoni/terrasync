# YAML Formatting Conventions

Apply these rules to all YAML files.

## Line Width

- Keep every line at 80 characters or fewer, including indentation.
- Wrap long scalar values across lines without changing meaning.
- Prefer folded block style (`>-`) for long prose values.
- Keep URLs and hashes on a single line when splitting would break value
  semantics.

## Structure and Style

- Use spaces for indentation; do not use tab characters.
- Do not apply key ordering changes unless explicitly requested.
- Preserve existing quoting style unless changing it improves correctness.
- Do not change data types while reformatting (string, number, boolean, null).
- Avoid reflowing values where whitespace is semantically significant.

## Safety

- Never change anchors, aliases, or merge keys semantics during formatting.
- Do not rewrite multiline literals (`|`) unless explicitly requested.
- Limit changes to formatting only unless the task requests functional edits.
