# Proposal

## Why

A session must not depend on what ran before it. Today `up` does not look for containers left
by an earlier session of the same scenario — an interrupted `run`, a killed terminal, an agent
that never called `down` — and `docker compose up -d` quietly reuses them: the world keeps the
agent where the last session left it, sim time does not start at 0, PX4 keeps its state. A test
then passes or fails depending on its predecessor. A second `up` of a scenario that is still in
use fails late, on the busy router port, instead of saying what is wrong.

Isolation between different scenarios already holds (own compose project, gz partition, router
port). Running the same scenario several times at once is not a goal.

## What Changes

- `up` (and so `run`) SHALL start from a clean state: if containers of the scenario's project
  exist, it SHALL refuse before starting anything, name the scenario as already running and
  point to `simops down`.
- `up --replace` SHALL tear the existing session down first and then start a fresh one.
- If the router port is taken by something else, `up` SHALL fail before starting containers,
  naming the port.

Out of scope: a session time-to-live (stopping forgotten sessions on its own), several
instances of one scenario at once.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sim-lifecycle`: `up` refuses an already running scenario, `--replace` starts over, a busy
  router port is reported before anything starts; sessions are isolated in time as well as
  between scenarios.

Depends on `baseline-simops` being archived, which creates `sim-lifecycle`.

## Impact

- `sim/simops.py`: `up`/`run` check the compose project and the port before `docker compose up`;
  new `--replace` flag.
- `sim/tests/`: unit tests for the checks; the Docker suite gets the stale-session case.
- AGENTS.md: the cleanup paragraph mentions `--replace`.
