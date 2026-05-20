## 1. Core Leg2 MAT Import

- [ ] 1.1 Add Leg2 ultrasonic datasource settings and loaded-data models in `user_tools/heatmap_alignment_core.py`
- [ ] 1.2 Implement Leg2 `.mat` loading for required fields `DataRecordCommon.timeOut`, `Ultrasonic.Distance`, `DataRecordCommon.ultrasonic_filtered`, and `DataRecordCommon.robustFC`
- [ ] 1.3 Normalize Leg2 time by removing erroneous trailing zero-time samples and subtracting the first retained time sample
- [ ] 1.4 Convert Leg2 ultrasonic distance arrays from millimeters to meters during import
- [ ] 1.5 Add validation errors that name missing required fields, incompatible array lengths, invalid time axes, and invalid numeric distance data while preserving any existing loaded datasource after failure
- [ ] 1.6 Add core tests for successful import, trailing zero-time cleanup, unit conversion, required filtered signal behavior, required robust segmentation, and failure cases

## 2. Session And Startup Persistence

- [ ] 2.1 Extend `AlignmentSession` JSON serialization/deserialization with optional Leg2 `.mat` datasource state, including path, visibility, selected signal kind, and Leg2-to-H5 offset
- [ ] 2.2 Preserve compatibility with older sessions that do not contain Leg2 datasource fields
- [ ] 2.3 Add a Leg2 `.mat` startup argument for the heatmap alignment GUI
- [ ] 2.4 Implement startup/session precedence so an explicit startup `.mat` replaces any Leg2 datasource stored in a loaded session
- [ ] 2.5 Add tests for session round-trip, older-session defaults, missing stored `.mat` reload handling, and startup override behavior

## 3. Timeline Integration

- [ ] 3.1 Extend the timeline state/range model to include an optional Leg2 track duration and Leg2-to-H5 offset without coupling it to the camera offset
- [ ] 3.2 Render a distinct colored Leg2 `.mat` timeline row when the datasource is loaded
- [ ] 3.3 Make the Leg2 timeline row draggable using the same offset sign convention and off-screen drag behavior as the camera row, refreshing dependent views on release
- [ ] 3.4 Ensure dragging the Leg2 row changes only the Leg2 offset and dragging the camera row changes only the camera offset
- [ ] 3.5 Display the current Leg2 offset or aligned track start value somewhere visible in the interface when the Leg2 datasource is loaded
- [ ] 3.6 Add tests for timeline bounds, offset sign convention, independent camera/Leg2 dragging, and timeline-to-Signals pixel alignment with the Leg2 track visible

## 4. Signals Plot Integration

- [ ] 4.1 Generalize the Signals plot data path enough to render the existing H5 peak-distance signal and one selected Leg2 ultrasonic signal together
- [ ] 4.2 Add a raw/filtered Leg2 ultrasonic selector that shows only one Leg2 ultrasonic signal at a time
- [ ] 4.3 Plot Leg2 ultrasonic data in aligned shared timeline coordinates using the Leg2 offset
- [ ] 4.4 Use a readable Leg2 plot color derived from the Leg2 timeline track color
- [ ] 4.5 Segment the plotted Leg2 signal into slightly transparent primary robust samples and lower-alpha non-robust samples using required `robustFC`
- [ ] 4.6 Preserve missing-value gaps in Leg2 ultrasonic plots
- [ ] 4.7 Update the compact legend to identify the selected Leg2 ultrasonic signal as raw or filtered
- [ ] 4.8 Add tests for signal selection, robust/non-robust segmentation, missing-value gaps, legend entries, and x-axis alignment in Timeline mode

## 5. GUI Resource Actions

- [ ] 5.1 Add interactive load and clear actions for the Leg2 `.mat` datasource
- [ ] 5.2 Report Leg2 `.mat` load failures with clear user-facing messages that include the missing or invalid field context
- [ ] 5.3 Keep camera video, H5 heatmap, and H5 peak-distance datasource state unchanged when loading, clearing, or failing to load a Leg2 `.mat`
- [ ] 5.4 Keep synced video export behavior and duration unchanged when a Leg2 ultrasonic datasource is loaded

## 6. Verification

- [ ] 6.1 Run focused tests with the repo-managed Hatch environment for heatmap alignment core and GUI behavior
- [ ] 6.2 Manually smoke-test loading a representative Leg2 `.mat`, switching raw/filtered display, dragging the Leg2 track, saving/loading a session, and launching with the `.mat` startup argument
- [ ] 6.3 Run `openspec validate add-leg2-mat-ultrasonic-datasource --strict`
