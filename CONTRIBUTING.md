# Contributing to VARYN

Thanks for exploring VARYN. It is an experimental prototype; the most useful contributions right now are **real reproducible feedback**, small isolated fixes, documentation corrections, and Windows compatibility reports.

## Where to start

1. Read the [README](README.md), [architecture notes](docs/ARCHITECTURE.md), and [security policy](SECURITY.md).
2. Review the [development PR](https://github.com/naraya07pedro-spec/VARYN/pull/1) before assuming the minimal `main` branch contains the app.
3. Search existing issues; create a **bug report** with OS version, exact commit, steps to reproduce, expected vs observed result, and **sanitized** logs.
4. For source development, use Python 3.12, a disposable virtual environment, and `python -m unittest discover -s tests -v` from the working source branch.
5. Make a small change per PR, add only relevant checks, and describe security implications. **Never** include live API keys, customer data, browser cookies, tokens, or real chat exports.
6. Use screenshots only from actual app runs, label mock/offline content clearly, and redact identifying information before sharing.

## Project direction

Priorities: practical owner-PC acceptance, transparent provider model billing, clear memory boundaries, and one coherent workflow. Synthetic test success is not proof of production readiness. Do not claim support for official consumer-app syncing without documented supported APIs and an independent real-world check.

We welcome thoughtful criticism and concrete reproduction cases. Do not create promotional issues just to inflate activity.
