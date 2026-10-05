## MODIFIED Requirements

### Requirement: What host code must use
Host ROS 2 code SHALL use rmw_zenoh to see the session's topics. Code that talks to an agent's
PX4 SHALL use `px4_msgs` generated from the firmware of that agent's platform (`version` or
`commit` in its `autopilot.px4`, after any base is applied): message type hashes are part of the
topic keys, so any other version sees no `/fmu/*` topics, without an error.

#### Scenario: Mismatched px4_msgs
- **WHEN** host code built with `px4_msgs` from another PX4 commit subscribes to `/fmu/out/...`
- **THEN** it receives nothing, and no error is reported
