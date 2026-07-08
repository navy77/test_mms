---
name: python-standards
description: Apply these standards whenever generating, editing, reviewing, or refactoring Python code.
---

# Python Standards

## Style
- Type hints on all function signatures
- Google-style docstrings on public functions
- Use pathlib instead of os.path
- Use f-strings instead of .format() or %
- Keep functions small and focused

## Imports
- Group imports: standard library, third-party, local
- Remove unused imports
- Avoid wildcard imports

## Typing
- Prefer built-in generic types (list[str], dict[str, int])
- Avoid Any unless necessary

## Error Handling
- Raise specific exceptions
- Never use bare except
- Include informative error messages


## Dependencies
- Use Poetry for dependency management
- Keep runtime and development dependencies separate
- Prefer compatible version constraints unless exact pinning is required

## Formatting
- Follow PEP 8
- Limit line length to 88 characters
- Use Black-compatible formatting
- Use Ruff for linting when available

## Naming
- Use descriptive variable and function names
- Classes use PascalCase
- Functions and variables use snake_case
- Constants use UPPER_SNAKE_CASE

## Functions
- Keep functions focused on a single responsibility
- Prefer early returns over deep nesting
- Avoid functions longer than ~50 lines unless justified

## Performance
- Prefer generators when appropriate
- Avoid unnecessary copies of large collections
- Use comprehensions when they improve readability

## Classes
- Use classes for objects with state and behavior
- Keep methods focused
- Use __init__ for setup, avoid logic
- Prefer composition over inheritance

## Security
- Never hardcode secrets or credentials
- Validate external input
- Use parameterized SQL queries
- Avoid shell=True with subprocess unless necessary

## Async
- Do not block the event loop
- Use asyncio.gather when appropriate
- Await all coroutines

## Logging
- Use the logging module
- Never use print for production code
- Include useful context in log messages

## Code Quality
- Avoid duplicated logic
- Prefer composition over inheritance when appropriate
- Remove dead code
- Keep modules cohesive

## Testing
- Use pytest, not unittest
- Use fixtures for reusable setup
- Parametrize test cases
- Use pytest.raises for exception testing
- Write at least one test per public function
- Cover edge cases
- Keep tests deterministic
- Mock external dependencies when appropriate

## AI Guidelines
- Do not introduce new dependencies unless necessary
- Preserve existing project conventions
- Minimize unrelated changes
- Explain non-obvious implementation choices
- Prefer modifying existing code over rewriting files