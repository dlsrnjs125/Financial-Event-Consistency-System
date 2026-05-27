# Contributing to Financial Event Consistency System

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone repository
git clone https://github.com/dlsrnjs125/Financial-Event-Consistency-System.git
cd Financial-Event-Consistency-System

# Initialize project
bash scripts/init.sh

# Install Python dependencies
pip install -r backend/requirements.txt
```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**
   ```bash
   git add .
   git commit -m "feat: Add your feature"
   ```

3. **Run tests locally**
   ```bash
   # Unit tests
   pytest backend/tests/unit -v
   
   # Consistency tests
   pytest backend/tests/consistency -v
   
   # All tests
   pytest backend/tests -v --cov
   ```

4. **Lint and format**
   ```bash
   flake8 backend/app
   black backend/app
   isort backend/app
   ```

5. **Push and create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Testing Requirements

- ✅ **Unit tests** must pass
- ✅ **Consistency tests** must pass
- ✅ **Lint** must pass
- ✅ **Coverage** should be > 80%
- ✅ **No hardcoded secrets** or credentials

## Commit Message Convention

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Test addition
- `chore`: Build, dependency updates
- `refactor`: Code refactoring

**Example:**
```
feat(idempotency): Add request hash validation

Add SHA256 hashing for idempotency key validation
to prevent different requests with same key.

Fixes #123
```

## Code Style

- Python: Follow PEP 8
- Use type hints
- Keep functions small and focused
- Write descriptive comments
- Add docstrings to public functions

## Testing Guidelines

### Unit Tests
- Test single functions in isolation
- Mock external dependencies
- Focus on business logic

### Integration Tests
- Test database interactions
- Test API endpoints
- Use fixtures for setup

### Consistency Tests
- Test duplicate prevention
- Test state machine rules
- Test concurrency scenarios

## Questions?

Open an issue or discussion on GitHub.

Thank you for contributing! 🙏
