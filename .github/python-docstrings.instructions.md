---
description: "Use when writing or updating Python docstrings, documenting Python functions, classes, methods, or modules."
applyTo: "**/*.py"
---
# Python Docstring Conventions

Follow PEP 8 and Google-style docstrings for all Python code.

## Formatting Rules

- Use Google-style docstring format
- Maximum 80 characters per line, including indentation
- Wrap long lines to stay within the 80-char limit
- Do NOT include usage examples (`Example:` sections)
- Always use imperative mood for the summary line per PEP 257
  (e.g., "Retrieve", not "Retrieves"; "Return", not "Returns")

## Structure

```python
def function_name(arg1: str, arg2: int) -> bool:
    """Summary line in imperative mood.

    Extended description if needed, wrapped at 80 characters
    including indentation.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something is invalid.
    """
```

## Section Order

1. Summary line (one line, no blank line after `"""`)
2. Blank line
3. Extended description (optional)
4. Blank line
5. `Args:` (if any parameters)
6. `Returns:` or `Yields:` (if applicable)
7. `Raises:` (if exceptions are raised)

## Module and Class Docstrings

```python
"""Short module summary.

Extended description of the module's purpose and contents,
wrapped at 80 characters.
"""
```

```python
class MyClass:
    """Short class summary.

    Extended description of the class.

    Attributes:
        attr1: Description of attr1.
        attr2: Description of attr2.
    """
```
