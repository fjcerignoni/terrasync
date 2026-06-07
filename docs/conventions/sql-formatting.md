# SQL Formatting Conventions

Apply these rules to all SQL files.

## Line Width

- Keep every line at 80 characters or fewer, including indentation.
- Break long expressions, predicates, and argument lists across lines.

## SQL Style

- Follow standard SQL formatting conventions.
- When applying formatting, never change the functionality or semantics of the
  query.
- Limit formatting changes to layout, casing, spacing, indentation, and adding
  explicit `as` for aliases when needed.
- Use lowercase for SQL keywords (`select`, `from`, `where`, `join`, etc.).
- When assigning aliases to columns or tables, always use `as` between the
  original name or expression and the alias.
- If an alias is written without `as`, add `as` rather than leaving the alias
  implicit.
- Do not enforce lowercase on comment text; comment casing is author-defined.
- Use consistent indentation for nested queries and conditional logic.
- Use spaces for indentation; do not use tab characters.
- Place each selected column and each major clause on its own line when helpful
  for readability.

## Comments

- Use `/* ... */` for comment blocks that span more than one line.
- Reserve `--` for single-line comments only.
- Never format, reflow, reindent, recase, or otherwise modify any content inside
  `/* ... */` comment blocks.
- Never format inline content that appears inside a comment block opening or
  closing line; comment text and embedded SQL examples must be kept exactly as
  written.

Example multi-line comment:

```sql
/*
This transformation normalizes supplier names
and applies deduplication by document ID.
*/
```
