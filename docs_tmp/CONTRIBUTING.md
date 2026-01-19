# Contributing to MCP Compose

Thank you for your interest in contributing to MCP Compose! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Development Workflow](#development-workflow)
5. [Coding Standards](#coding-standards)
6. [Testing Guidelines](#testing-guidelines)
7. [Documentation](#documentation)
8. [Pull Request Process](#pull-request-process)
9. [Release Process](#release-process)

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- Git
- Docker (optional, for testing containerization)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/mcp-compose.git
cd mcp-compose
```

3. Add the upstream repository:

```bash
git remote add upstream https://github.com/datalayer/mcp-compose.git
```

## Development Setup

### Python Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Verify installation
mcp-composer --version
```

### UI Development Setup

```bash
# Navigate to UI directory
cd ui

# Install dependencies
npm install

# Start development server
npm run dev

# In another terminal, start the backend
cd ..
mcp-composer serve --config examples/mcp_compose.toml
```

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Development Workflow

### Branch Strategy

- `main` - Stable, production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `release/*` - Release preparation

### Creating a Feature Branch

```bash
# Update your local repository
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/my-new-feature

# Make your changes
# ...

# Commit your changes
git add .
git commit -m "feat: add my new feature"

# Push to your fork
git push origin feature/my-new-feature
```

### Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

**Examples:**
```bash
feat(api): add server restart endpoint
fix(ui): resolve dashboard loading issue
docs(readme): update installation instructions
test(composer): add process manager tests
```

## Coding Standards

### Python Code Style

We follow [PEP 8](https://pep8.org/) and use:
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **flake8** for linting

```bash
# Format code
black mcp_compose tests

# Sort imports
isort mcp_compose tests

# Type check
mypy mcp_compose

# Lint
flake8 mcp_compose tests
```

### TypeScript/React Code Style

- Use TypeScript for all new code
- Follow React best practices
- Use functional components with hooks
- Prefer composition over inheritance

```bash
# In ui/ directory

# Lint
npm run lint

# Format
npm run format

# Type check
npm run type-check
```

### Code Guidelines

**Python:**
- Use type hints for all function signatures
- Write docstrings for all public functions/classes
- Keep functions small and focused
- Use async/await for I/O operations
- Follow SOLID principles

**TypeScript/React:**
- Use descriptive component names
- Extract reusable logic into hooks
- Keep components under 300 lines
- Use proper prop types
- Avoid inline styles

## Testing Guidelines

### Running Tests

```bash
# Run all Python tests
pytest

# Run with coverage
pytest --cov=mcp_compose --cov-report=html

# Run specific test file
pytest tests/test_composer.py

# Run specific test
pytest tests/test_composer.py::test_compose_from_config

# Run UI tests
cd ui
npm test
```

### Writing Tests

**Python:**
```python
import pytest
from mcp_compose import MCPServerComposer

def test_composer_initialization():
    """Test that composer initializes correctly."""
    composer = MCPServerComposer(name="test-composer")
    assert composer.name == "test-composer"

@pytest.mark.asyncio
async def test_async_composition():
    """Test async server composition."""
    composer = MCPServerComposer()
    # Test implementation
```

**TypeScript/React:**
```typescript
import { render, screen } from '@testing-library/react';
import { Dashboard } from './Dashboard';

test('renders dashboard with metrics', () => {
  render(<Dashboard />);
  const heading = screen.getByText(/Dashboard/i);
  expect(heading).toBeInTheDocument();
});
```

### Test Coverage Requirements

- New code must have at least 80% coverage
- Critical paths must have 100% coverage
- Include edge cases and error conditions
- Write integration tests for complex workflows

## Documentation

### Code Documentation

**Python:**
```python
def start_server(self, server_name: str, timeout: int = 30) -> bool:
    """
    Start a managed MCP server.
    
    Args:
        server_name: Name of the server to start
        timeout: Maximum time to wait for server start (seconds)
        
    Returns:
        True if server started successfully, False otherwise
        
    Raises:
        ServerNotFoundError: If server is not configured
        ServerStartError: If server fails to start
        
    Example:
        >>> composer = MCPServerComposer()
        >>> composer.start_server("filesystem")
        True
    """
```

**TypeScript:**
```typescript
/**
 * Fetches server status from API
 * 
 * @param serverId - Unique identifier of the server
 * @returns Promise resolving to server status
 * @throws {ApiError} When server is not found or request fails
 * 
 * @example
 * ```typescript
 * const status = await fetchServerStatus("filesystem");
 * console.log(status.state); // "running"
 * ```
 */
async function fetchServerStatus(serverId: string): Promise<ServerStatus>
```

### User Documentation

When adding features, update:
- `docs/USER_GUIDE.md` - User-facing functionality
- `docs/API_REFERENCE.md` - API endpoints or Python API
- `docs/DEPLOYMENT.md` - Deployment-related changes
- `README.md` - Major features or changes

### Documentation Style

- Use clear, concise language
- Include code examples
- Add screenshots for UI features
- Explain "why" not just "how"
- Keep it up to date

## Pull Request Process

### Before Submitting

1. **Run Tests:**
```bash
make test
make test-ui
```

2. **Check Coverage:**
```bash
make test-coverage
```

3. **Lint and Format:**
```bash
make lint
make format
```

4. **Update Documentation:**
- Add/update docstrings
- Update relevant docs
- Add changelog entry

### Submitting PR

1. Push your branch to your fork
2. Create Pull Request on GitHub
3. Fill out the PR template
4. Link related issues
5. Request review from maintainers

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added new tests
- [ ] Updated existing tests

## Documentation
- [ ] Updated docstrings
- [ ] Updated user docs
- [ ] Updated API docs

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] No new warnings generated
- [ ] Tests added for new code
- [ ] All tests pass
```

### Review Process

1. Automated checks run (CI/CD)
2. Maintainer reviews code
3. Requested changes addressed
4. Approval from maintainer
5. Merge to main/develop

### After Merge

1. Delete your feature branch
2. Update your fork:
```bash
git checkout main
git pull upstream main
git push origin main
```

## Release Process

### Version Numbers

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Update `docs/CHANGELOG.md`
4. Run full test suite
5. Build and test Docker image
6. Create release branch
7. Create GitHub release
8. Publish to PyPI
9. Publish Docker image
10. Announce release

## Getting Help

### Questions?

- 💬 [GitHub Discussions](https://github.com/datalayer/mcp-compose/discussions)
- 🐛 [Issue Tracker](https://github.com/datalayer/mcp-compose/issues)
- 📧 Email: support@datalayer.ai

### Reporting Bugs

Use the bug report template:
- Clear description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details
- Logs/screenshots

### Requesting Features

Use the feature request template:
- Clear description
- Use case
- Proposed solution
- Alternatives considered

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation

Thank you for contributing to MCP Compose! 🎉

---

*For more information, see our [documentation](docs/) or visit [datalayer.ai](https://datalayer.ai)*
