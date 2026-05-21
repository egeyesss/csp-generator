---
name: Bug report
about: Something is producing wrong output, crashing, or behaving inconsistently
title: ''
labels: bug
assignees: ''
---

## What happened

A clear description of what you observed.

## What you expected

What should have happened instead.

## Reproduction

Smallest set of steps that triggers the bug. Include the CLI command if relevant.

```bash
# e.g.
csp-generator generate --theme classic_houses --seed 7
```

If the bug is in a generated puzzle, paste the full puzzle JSON (or a link to it) so we can re-run the solver and propagator against it.

## Environment

- OS:
- Python version: `python --version`
- csp-generator version / commit:
- OR-Tools version: `pip show ortools | grep -i version`

## Additional context

Stack trace, log output, screenshots — anything that helps narrow down the cause.
