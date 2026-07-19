# Contributing to M.I.C.A AI Assistant

Thank you for your interest in contributing to M.I.C.A! This document provides guidelines and instructions for contributors.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Virtual environment (recommended)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/M.I.C.A.git
   cd M.I.C.A
   ```

3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/Koch-Nico1312/M.I.C.A.git
   ```

## Development Setup

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Development Dependencies

```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock pytest-benchmark
pip install flake8 mypy black isort bandit
```

### Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys

3. Configure `config.yaml` as needed

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use type hints for all function signatures
- Docstrings for all public functions and classes

### Formatting

Use Black for code formatting:

```bash
black core actions memory config tests
```

### Import Sorting

Use isort for import sorting:

```bash
isort core actions memory config tests
```

### Linting

Use flake8 for linting:

```bash
flake8 core actions memory config tests
```

### Type Checking

Use mypy for type checking:

```bash
mypy core actions memory config
```

## Testing

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_dependency_injection.py
```

### Run with Coverage

```bash
pytest --cov=core --cov=actions --cov=memory --cov=config --cov-report=html
```

### Run Specific Test Category

```bash
pytest -m unit  # Unit tests only
pytest -m integration  # Integration tests only
pytest -m performance  # Performance benchmarks
```

### Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

### Writing Tests

1. Place tests in the `tests/` directory
2. Name test files: `test_*.py`
3. Name test functions: `test_*()`
4. Use the mocking utilities from `tests/mocking_utils.py`

Example:

```python
import pytest
from tests.mocking_utils import mock_config

def test_my_function(mock_config):
    # Arrange
    mock_config.get.return_value = "test_value"

    # Act
    result = my_function()

    # Assert
    assert result == "expected"
```

## Submitting Changes

### Branch Strategy

1. Create a new branch from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/my-feature
   ```

2. Make your changes

3. Commit with descriptive messages:
   ```bash
   git add .
   git commit -m "Add new feature: description"
   ```

### Commit Message Format

Use conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks

Example:
```
feat(core): add dependency injection system

Add a service container for managing component lifecycles
and dependencies. This improves testability and modularity.

Closes #123
```

### Push and Create Pull Request

1. Push to your fork:
   ```bash
   git push origin feature/my-feature
   ```

2. Create a pull request on GitHub

3. Fill in the PR template:
   - Describe your changes
   - Link related issues
   - Add screenshots if applicable
   - Confirm that tests pass

### Pull Request Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Type hints added where appropriate
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)
- [ ] No merge conflicts with upstream/main

## Reporting Issues

### Bug Reports

When reporting a bug, include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Steps to reproduce the issue
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Environment**:
   - OS and version
   - Python version
   - M.I.C.A version
6. **Logs**: Relevant log output
7. **Screenshots**: If applicable

### Issue Template

```markdown
**Description**
[Clear description of the issue]

**Steps to Reproduce**
1. Step 1
2. Step 2
3. ...

**Expected Behavior**
[What you expected]

**Actual Behavior**
[What actually happened]

**Environment**
- OS: [e.g., Windows 11, Ubuntu 22.04]
- Python: [e.g., 3.11.0]
- M.I.C.A: [e.g., v1.0.0]

**Logs**
```
[Paste relevant logs here]
```
```

## Feature Requests

### Proposing a Feature

Before proposing a feature:

1. Check existing issues to avoid duplicates
2. Consider if it fits the project scope
3. Think about implementation complexity
4. Consider maintenance burden

### Feature Request Template

```markdown
**Feature Description**
[Clear description of the feature]

**Use Case**
[Why is this feature needed? What problem does it solve?]

**Proposed Implementation**
[How do you envision this being implemented?]

**Alternatives Considered**
[What alternatives did you consider? Why did you choose this approach?]

**Additional Context**
[Any other relevant information]
```

## Development Guidelines

### Adding New Actions

1. Inherit from `BaseAction` in `actions/base_action.py`
2. Implement required methods: `execute()`, `validate_parameters()`, `metadata`
3. Add tool declaration to `tools/tool_declarations.py`
4. Write tests in `tests/`
5. Update documentation

Example:

```python
from actions.base_action import BaseAction, ActionMetadata, ActionPermission

class MyAction(BaseAction):
    @property
    def metadata(self):
        return ActionMetadata(
            name="my_action",
            description="Description of my action",
            permission=ActionPermission.MEDIUM
        )

    def execute(self, parameters):
        # Implementation
        return "Result"

    def validate_parameters(self, parameters):
        # Validation logic
        return True
```

### Adding New Core Services

1. Create service in `core/`
2. Add singleton getter function
3. Register in dependency injection container
4. Write tests
5. Update documentation

### Adding Plugins

1. Create plugin file in `plugins/`
2. Implement `register()` function
3. Register actions with plugin manager
4. Add documentation

Example:

```python
# plugins/my_plugin.py

def register(plugin_manager):
    plugin_manager.register_action(MyAction())
```

### Modifying Configuration

1. Update `config.yaml` with new settings
2. Update `.env.example` if adding environment variables
3. Update `config/config_loader.py` if needed
4. Document changes in CHANGELOG

## Code Review Process

### For Contributors

1. Be responsive to review comments
2. Address all feedback
3. Keep PRs focused and small
4. Be patient with the review process

### For Reviewers

1. Be constructive and respectful
2. Explain the reasoning for suggestions
3. Focus on code quality and design
4. Test the changes if possible

## Release Process

Releases are managed by maintainers:

1. Update version in appropriate files
2. Update CHANGELOG
3. Create git tag
4. Build and publish release
5. Announce release

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on what is best for the community
- Show empathy towards other community members

### Communication

- Use GitHub for discussions
- Be clear and concise
- Use appropriate channels for different topics
- Respect others' time

## Getting Help

### Documentation

- [Architecture.md](Architecture.md) - System architecture
- [API.md](API.md) - API documentation
- [Troubleshooting.md](Troubleshooting.md) - Troubleshooting guide
- [Performance Guide.md](Performance-Guide.md) - Performance optimization

### Questions

- Open a GitHub Discussion for questions
- Check existing issues first
- Provide context and details

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS file
- Release notes
- Project documentation

Thank you for contributing to M.I.C.A!
