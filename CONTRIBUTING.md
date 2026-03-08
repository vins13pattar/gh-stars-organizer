# Contributing to gh-stars-organizer

Thanks for your interest in contributing.

## Setup

1. Fork and clone the repo
2. Create a virtual environment
3. Install dev dependencies:

```bash
pip install -e ".[dev]"
```

## Development Workflow

- Create a feature branch
- Keep changes focused
- Add/adjust tests for behavior changes
- Run `pytest -q` before opening a PR

## Pull Request Checklist

- Tests added/updated
- Documentation updated
- No unrelated changes
- Clear PR description and motivation

## Code Style

- Python 3.11+
- Type hints for new modules
- Prefer small, composable functions

## Release & Versioning

This project uses tag-based versioning with `hatch-vcs`.

- Create a release tag like `v1.0.1`
- Push the tag and publish a GitHub Release
- The publish workflow builds and releases the matching version to PyPI
