# Contributing

Thank you for contributing to ClawChain.

## Development setup

1. Install backend dependencies:
   - `cd backend && pip install -r requirements.txt`
2. Install frontend dependencies:
   - `cd frontend && npm install`
3. Run backend:
   - `cd backend && python cli.py serve`
4. Run frontend:
   - `cd frontend && npm run dev`

## Contribution scope

- Keep the project webchat-first and local-first
- Avoid introducing capability claims that runtime cannot satisfy
- Keep prompts, templates, tools, and docs consistent

## Pull request checklist

- [ ] No secrets, runtime logs, personal sessions, or local configs included
- [ ] Docs updated for behavior/config changes
- [ ] Prompt text and runtime behavior remain aligned
- [ ] Tests/build pass for changed areas

## Commit style

- Prefer focused commits by concern (runtime, docs, cleanup)
- Use clear intent in commit messages (why, not only what)
