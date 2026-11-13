# Source verification on 13 November 2026

This record covers the source prepared for the new repository. It is not a live deployment report.

| Check | Result |
| --- | --- |
| Full Linux backend/security/integration suite | 330 passed, 5 skipped; 239.48 seconds |
| Focused Windows alert/archive/runtime regressions | 36 passed, 1 skipped |
| Linux warnings | Four SQLAlchemy Query.get deprecations; no failed assertions |
| External effects | Tests block actual SMTP/network effects and use isolated data |
| Fresh AWS, browser and full MySQL runs | Not performed in this publishing task; see historical reports |

The Linux skips require MySQL row locking or local MySQL client tools. The Windows suite initially encountered restricted-sandbox file rename permissions; the successful rerun outside that sandbox retained mocked external effects. The alert and disk-monitor code is prepared locally, not installed on AWS.

## Reproduce in an isolated environment

Install `requirements-test.txt` with `requirements-lock.txt` as constraints. With no production database configured as a test target, run:

```sh
python -m pytest tests --ignore=tests/e2e -q --tb=short
```

Use a dedicated local QA MySQL database for the skipped database-specific cases. Never use the production database. Credentials, customer uploads, local virtual environments, raw QA artifacts and recovery archives are not repository content.

## Evidence integrity

Original JUnit files are retained locally. Their SHA-256 values are:

- `prepublish-linux-20261113.xml`: `f4bfb1e7327569d82d96ce115e612343d62ff72d18c091aac2b9d0c1fec976b1`
- `prepublish-windows-20261113.xml`: `f883376c14f9a05614497b7c185b95bee6c45703c0fb0896cd5350aa49a42e04`
