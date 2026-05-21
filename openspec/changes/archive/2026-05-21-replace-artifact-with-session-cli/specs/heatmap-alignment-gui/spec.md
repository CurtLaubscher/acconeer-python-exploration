## ADDED Requirements

### Requirement: Session startup CLI
The system SHALL allow the heatmap alignment GUI to load a saved alignment session on startup using a session-specific command-line argument.

#### Scenario: Load session on startup
- **WHEN** the user launches the heatmap alignment GUI with a saved alignment session path passed to `--session`
- **THEN** the system loads that saved alignment session during startup

#### Scenario: Session startup takes precedence over source startup arguments
- **WHEN** the user launches the heatmap alignment GUI with `--session` and individual camera or H5 startup arguments
- **THEN** the system loads the saved alignment session as the source of camera, H5, viewport, render, and alignment state rather than partially overriding it with the individual camera or H5 arguments

#### Scenario: Optional datasource startup arguments may override session datasources
- **WHEN** the user launches the heatmap alignment GUI with `--session` and an explicit optional datasource startup argument such as peak-distance JSON or Leg2 MAT
- **THEN** the system loads the saved alignment session first and then applies the explicit optional datasource startup argument using the same override behavior as the corresponding datasource requirement

#### Scenario: Reject legacy artifact startup argument
- **WHEN** the user launches the heatmap alignment GUI with the legacy `--artifact` startup argument
- **THEN** the command-line parser rejects the argument and presents help that lists `--session` as the saved alignment session startup argument
