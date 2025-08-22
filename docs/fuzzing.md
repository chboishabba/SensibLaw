# Fuzzing

`scripts/fuzz_section_parser.py` uses [Atheris](https://pypi.org/project/atheris/)
to fuzz the HTML section parser.  Random byte sequences are decoded as UTF-8 and
fed to `parse_section`; any uncaught exception will cause the fuzzer to report a
crash.

## Local execution

Install the dependency and run the harness for a bounded time:

```bash
python -m pip install atheris
python scripts/fuzz_section_parser.py -max_total_time=30
```

This example runs for 30 seconds and saves any crashing inputs as `crash-*`
files in the current directory.

## Continuous fuzzing

The repository includes a GitHub Actions workflow
(`.github/workflows/fuzz.yml`) that executes the fuzzer on a weekly schedule and
on demand.  The workflow fails if a crash is detected, ensuring any issues are
surfaced promptly.
