# Context Handoff

## Current Objective

Project: `/Users/cosmos/agent-demo`. Current task: run the local pet agent product loop and desktop pet.

## Current State

The local product loop is running via:

```bash
PET_AGENT_API_URL=http://127.0.0.1:8000 python3 run_pet_agent.py --no-reload
```

It was started outside the sandbox because binding `127.0.0.1:8000` failed inside the sandbox with `operation not permitted`. The launcher session is still active and owns:

- FastAPI backend at `http://127.0.0.1:8000`.
- Telegram bot process, with logs at `logs/telegram_bot.log`.

The macOS floating desktop pet is also running via:

```bash
python3 launch_desktop_pet.py --pet-id 2
```

Pet `2` is `Qing Qing`, a virtual pet with ready desktop assets in `static/desktop_pet_assets/8bb2abb559984f83812153d08feede54/`.

Important constraint: the worktree already has many unrelated dirty files and generated assets. Do not revert or clean them unless explicitly asked.

## Artifact Trail

Files changed/read in the latest turn:

- `.agents/context-handoff.md`
- `README.md`
- `api.py`
- `run_pet_agent.py`
- `launch_desktop_pet.py`
- logs: `logs/fastapi.log`, `logs/telegram_bot.log`

## Verification

Completed checks:

- `curl -sS http://127.0.0.1:8000/pets` returned 3 local virtual pets.
- `curl -sS http://127.0.0.1:8000/virtual-pets/2` returned pet `2` state successfully.
- FastAPI log shows `Uvicorn running on http://127.0.0.1:8000`.
- Both the product-loop session and desktop-pet session remained running after startup.

No code tests were run because this turn only started existing services and updated this handoff.

## Next Step

Use `http://127.0.0.1:8000` for local API checks. To stop the running product loop or desktop pet, terminate their active terminal sessions or kill the corresponding processes.
