import subprocess


def test_eval_goldset_cli_succeeds():
    cmd = [
        "python",
        "-m",
        "cli",
        "eval",
        "goldset",
        "--threshold",
        "0.9",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(
            f"Command failed with exit code {completed.returncode}:\n"
            f"STDOUT: {completed.stdout}\nSTDERR: {completed.stderr}"
        )
