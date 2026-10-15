# Contributing to Givlah

Thanks for your interest in Givlah. Bug reports, ideas and pull requests are all welcome.

## Before you start

- Read [docs/PRODUCT.md](docs/PRODUCT.md) for scope and [docs/SPECIFICATION.md](docs/SPECIFICATION.md) for how the app must behave. If a change alters behaviour described in the specification, update the specification in the same pull request.
- For anything larger than a small fix, please open an issue first so the approach can be agreed before you spend time on it.
- Report security problems privately as described in [SECURITY.md](SECURITY.md), not in public issues.

## Development setup

You need Python 3.12 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open http://localhost:8000. To populate clearly labelled synthetic demo data, run `python manage.py load_demo`.

Run the tests with:

```bash
python manage.py test
```

Tests must not make network calls or need credentials.

## Ground rules

These rules come from the specification. Please keep them intact:

- **Coordination state changes only through service functions** in `apps/*/services.py`. Views, forms and admin actions call services. They never modify plans, reservations, confirmations or handovers directly.
- **Private details stay private.** Exact pickup or destination details must only be read through the permission-checked selectors. Never put them in public templates, URLs, logs or event text.
- **Identity comes from the session**, never from posted user IDs.
- **No GET requests that change data.** Every mutation is a CSRF-protected POST.
- **Photos are stored only after sanitizing.** Never save or serve an original upload.
- **Keep dependencies minimal.** If a new dependency is needed, explain why in the pull request.

## Style

- Follow the existing code style: PEP 8, clear names, small functions and comments only where the reason isn't obvious.
- Write templates for phones first, and keep them working without JavaScript.
- Never use colour as the only signal of state, and keep text contrast readable.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
- Keep each pull request focused on one change, with tests that would catch the bug or regression it addresses.
- Describe what changed, why and how you checked it.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
