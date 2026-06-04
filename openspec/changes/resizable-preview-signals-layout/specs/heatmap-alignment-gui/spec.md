## ADDED Requirements

### Requirement: Resizable Preview and Signals layout
The system SHALL allow the user to adjust the vertical space allocated to the Preview area and the Signals plot in the heatmap alignment workbench.

#### Scenario: Resize Preview and Signals vertically
- **WHEN** the user drags the divider between the Preview area and the Signals plot
- **THEN** the system reallocates vertical space between the Preview area and the Signals plot without changing the loaded resources, current time, alignment offsets, viewport geometry, or plotted signal data

#### Scenario: Preserve horizontal Preview resizing
- **WHEN** the user adjusts the vertical allocation between Preview and Signals
- **THEN** the existing horizontal resize behavior between Camera Video and the viewport/rendered-heatmap preview column remains available

#### Scenario: Keep Timeline fixed for current workflow
- **WHEN** the user adjusts the vertical allocation between Preview and Signals
- **THEN** the Timeline remains a fixed-height control area outside the Preview/Signals resize interaction

#### Scenario: Do not persist splitter sizes
- **WHEN** the user changes the Preview/Signals vertical allocation and later launches the workbench again
- **THEN** the system uses the default layout allocation rather than restoring the prior Preview/Signals splitter position
