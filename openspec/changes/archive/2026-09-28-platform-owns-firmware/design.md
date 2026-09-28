# Design

## Context

Today `Environment.autopilot.px4` is a `PX4Firmware` (repo, version, commit, with its offline
checks), and `Platform.load` reads `agent.yaml` by hand, taking only
`autopilot.px4.airframe` and leaving it `None` when it is missing, so `compose` would write
`PX4_SYS_AUTOSTART: "None"`. `build` resolves the one firmware once and passes `(ref, commit)` to
`compose`, which gives every `px4-<agent>` service the same image. The platform is loaded inside
the `Agent` validator, so anything `Platform.load` raises as a `ValueError` ends up in the
environment's single `InvalidEnvironment` message under `agents.<name>.platform`.

## Goals / Non-Goals

**Goals:**
- `agent.yaml` is a validated document with the same rules and messages for the firmware as
  today, plus a required airframe.
- One resolution and one image per distinct firmware, however many agents or platforms name it.

**Non-Goals:**
- A platform without an autopilot (the next change, `agents-without-autopilot`, relaxes the
  required `autopilot.px4`).
- Any override of the platform's firmware from the environment.

## Decisions

**`agent.yaml` is a pydantic model, and the platform's PX4 block extends `PX4Firmware`.**
`autopilot.px4` in `agent.yaml` is flat (`version`, `commit`, `repo`, `airframe` side by side), so
the model is `PX4Autopilot(PX4Firmware)` with a required `airframe: int`. It inherits the `ref`
message, the "not both" check, the SHA and version checks and the 1.18 minimum unchanged, and the
messages already name `autopilot.px4.<key>`, which is where they sit in `agent.yaml` too. It gets
a `firmware` property returning the plain `PX4Firmware` (repo, version, commit): the key for
resolving, so two platforms with the same firmware and different airframes share one
resolution. `Platform` holds `px4: PX4Autopilot` instead of `px4_airframe`. Alternative: nest
the firmware (`px4: {firmware: {...}, airframe}`), rejected because the file the user writes
would get a level that means nothing to them.

**`autopilot` and `px4` are required in `agent.yaml` for now.** A missing airframe fails loading
instead of reaching compose as `None`. The next change makes them optional and skips the PX4
service.

**`Platform.load` reports its own file.** It validates `agent.yaml` with `extra="forbid"` and turns
a `ValidationError` into one `ValueError` that starts with the `agent.yaml` path and describes
each error the way `Environment.load` does. The describing function moves out of
`environment.py` to where both can import it without a cycle (`environment` imports `agent`
imports `platform`), taking the document's name for the unknown-key message ("is not a key
agent.yaml defines"). The environment's message then reads
`<environment>: agents.rover1.platform: <agent.yaml>: <what>`.

**The old keys `autopilot` and `world.room` get their own messages**, like `robots`: a
before-validator says the firmware is now set in each platform's `agent.yaml`, and one on the
world says `room` is now `generate_room`. The generic unknown-key message would not tell either:
the firmware moved to another file, and for `world.room` pydantic reports only the unknown key,
without the "exactly one world source" message (an after-validator does not run once a field
has failed).

**`World.room` becomes `World.generate_room`; `RoomSpec` keeps its name.** The glossary term is
the room spec; `generate_room` is only the key. `generate_maze` will sit next to it.

**`build` resolves per distinct firmware; `compose` takes the resolutions.** `build` collects
each agent's `platform.px4.firmware`, resolves each distinct one once (a dict keyed by the
frozen, hashable `PX4Firmware`) and prints one `PX4 <tag> = <commit>` line per firmware.
`compose(environment, world_stem, world_name, firmware)` takes that dict, and each `px4-<agent>`
gets its build args and image tag from its own platform's firmware. The image tag stays the
commit's first 12 characters, so identical firmware is one image.

**`rover_differential_lidar_px4/agent.yaml` pins `version: v1.18.0-rc1`**, with the comment about
`px4_msgs` type hashes that today sits in `rover_room.yaml`: the platform is where the pin
matters now.

## Risks / Trade-offs

- [Agents on platforms with different firmware need host code with two `px4_msgs`] → stated in
  `host-access`; the one platform here has one firmware.
- [Each distinct version in the same repository is a separate `git ls-remote`] → one call per
  firmware at `build`; cache by repository only if several firmwares become common.
- [Environments outside the repo break (`autopilot`, `world.room`)] → both fail loading with
  messages that say what to write instead; no silent change.

## Migration Plan

Rewrite `environments/rover_room.yaml` in the new format (the sketch `rover_env_spec.yaml`),
move its firmware into the platform's `agent.yaml`, remove the sketch. PX4 images are tagged by
commit, so the same `v1.18.0-rc1` keeps using the image already built. Rollback: revert the
commit.
