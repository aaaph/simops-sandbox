# Proposal

## Why

A session must not depend on what ran before it. Today `up` does not look for containers left
by an earlier session of the same environment — an interrupted `run`, a killed terminal, an agent
that never called `down` — and `docker compose up -d` quietly reuses them: the world keeps the
agent where the last session left it, sim time does not start at 0, PX4 keeps its state. A test
then passes or fails depending on its predecessor. A second `up` of an environment whose session is still in
use fails late, on the busy router port, instead of saying what is wrong.

Isolation between sessions of different environments already holds (own compose project, gz partition, router
port). Running the same environment several times at once is not a goal.

## What Changes

- `up` (and so `run`) SHALL start from a clean state: if containers of the environment's project
  exist, it SHALL refuse before starting anything, name the environment's session as already running and
  point to `simops down`.
- `up --replace` SHALL tear the existing session down first and then start a fresh one.
- If the router port is taken by something else, `up` SHALL fail before starting containers,
  naming the port.

Out of scope: a session time-to-live (stopping forgotten sessions on its own), several
sessions of one environment at once.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sim-lifecycle`: `up` refuses an environment whose session is already running, `--replace` starts over, a busy
  router port is reported before anything starts; sessions are isolated in time as well as
  between environments.

Depends on `baseline-simops` being archived, which creates `sim-lifecycle`.

## Impact

- `src/simops/session.py`: `up`/`run` check the compose project and the port before `docker compose up`;
  new `--replace` flag.
- `tests/simops/`: unit tests for the checks; the Docker suite gets the stale-session case.
- AGENTS.md: the cleanup paragraph mentions `--replace`.
