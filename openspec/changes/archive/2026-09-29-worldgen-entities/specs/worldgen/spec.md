# Spec Delta

## Purpose

worldgen generates SDF worlds for a simulation from typed parts — walls, obstacles, the start
marker — and guarantees that a generated room is passable and reachable for a robot of a given
clearance. It knows nothing of simops.

## ADDED Requirements

### Requirement: An SDF world is assembled from parts
worldgen SHALL build an SDF world from a name and a list of parts — walls, obstacles and the start
marker — each part rendering its own SDF model. Every world SHALL share the same envelope
(physics, sensor systems, GUI, arrow-key drive, sun, ground plane) whatever parts it holds, and
SHALL contain no agents. An open field is a world whose only part is the start marker.

#### Scenario: Open field
- **WHEN** an open field is generated
- **THEN** the world's models are the ground plane and the start marker, with no wall and no
  obstacle

#### Scenario: Same envelope for every world
- **WHEN** a room and an open field are generated
- **THEN** both worlds hold the same physics, systems and ground plane, and neither holds an agent

### Requirement: A wall is given by a segment
A wall SHALL be definable by the segment from point A to point B at floor level: its model runs
along that segment, is extended by half the wall's thickness beyond each end, and has the wall's
thickness and height. Two walls sharing an end point SHALL therefore leave no gap at that corner.
A room's walls are the four segments between its corners.

#### Scenario: Wall along a segment
- **WHEN** a wall is given from (0, 0) to (0, 4) with thickness 0.15
- **THEN** its model is centred at (0, 2), 4.15 long, 0.15 thick and turned to run along y

#### Scenario: Room walls are joined with no gap
- **WHEN** a room of size 10 x 8 is generated with walls 0.15 thick
- **THEN** every point of the frame between the rectangles 9.85 x 7.85 and 10.15 x 8.15 around
  the origin — its outer corners included — lies inside at least one wall model

### Requirement: An obstacle is a footprint with a shape
An obstacle SHALL be a footprint — a disc given by its position and radius — and a shape drawn
inscribed in that disc: a box (its half-diagonal equal to the radius) or a cylinder (of that
radius). Changing an obstacle's shape SHALL keep its footprint, so a room stays passable and
reachable whatever shapes its obstacles are given. A box obstacle given no proportions SHALL be
square.

#### Scenario: Box inscribed in the footprint
- **WHEN** a box obstacle of radius 0.4 is rendered
- **THEN** its half-diagonal is 0.4

#### Scenario: Changing the shape keeps the footprint
- **WHEN** a cylinder obstacle is turned into a box
- **THEN** the obstacle keeps its position and radius, and the box is square and inscribed in its
  disc

### Requirement: A room is passable and reachable
A generated room SHALL have walls around it and obstacles scattered inside, every gap between
obstacle footprints and walls at least the clearance wide, a free disc of the spawn clearance
around the origin, and every free cell reachable from the origin by a robot of that clearance.
If the reachability check fails, generating SHALL fail with an error saying how many free cells
are walled off. The same seed SHALL give the same room.

#### Scenario: Same seed, same room
- **WHEN** a room is generated twice with the same seed, size and clearance
- **THEN** both worlds are identical, and a different seed gives a different world

#### Scenario: Walled-off cells are reported
- **WHEN** a row of obstacles cuts the room in two
- **THEN** the reachability check counts the free cells beyond it as walled off
