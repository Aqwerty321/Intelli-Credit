# Knowledge Block: Bootstrap

## Summary
- **Attempted:** Full environment bootstrap for WSL2 Ubuntu + RTX 5090 (Blackwell sm_100, CUDA 13.1)
- **Key facts:** Driver 591.86, CUDA 13.1, 24463 MiB VRAM total, ~21245 MiB used at idle (Windows overhead + other processes)
- **Outcome:** Scripts generated. Pending execution and GPU passthrough verification.
- **Next:** Run `scripts/bootstrap.sh`, verify Docker GPU access, then `scripts/setup_pyenv.sh`

## Logs
- `logs/bootstrap/bootstrap_*.log` — APT install, Docker, nvidia-ctk logs
- `logs/bootstrap/setup_pyenv_*.log` — pyenv installation logs
