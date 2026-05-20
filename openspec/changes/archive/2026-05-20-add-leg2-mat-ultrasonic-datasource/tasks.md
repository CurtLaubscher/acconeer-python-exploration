## 1. Core Leg2 MAT Import

- [x] 1.1 Add Leg2 ultrasonic datasource settings and loaded-data models in `user_tools/heatmap_alignment_core.py`
- [x] 1.2 Implement Leg2 `.mat` loading for required fields `DataRecordCommon.timeOut`, `Ultrasonic.Distance`, `DataRecordCommon.ultrasonic_filtered`, and `DataRecordCommon.ReliableFlag`
- [x] 1.3 Normalize Leg2 time by removing erroneous trailing zero-time samples and subtracting the first retained time sample
- [x] 1.4 Convert Leg2 ultrasonic distance arrays from millimeters to meters during import
- [x] 1.5 Add validation errors that name missing required fields, incompatible array lengths, invalid time axes, and invalid numeric distance data while preserving any existing loaded datasource after failure
- [x] 1.6 Add core tests for successful import, trailing zero-time cleanup, unit conversion, required filtered signal behavior, required `DataRecordCommon.ReliableFlag` segmentation, and failure cases

## 2. Session And Startup Persistence

- [x] 2.1 Extend `AlignmentSession` JSON serialization/deserialization with optional Leg2 `.mat` datasource state, including path, visible flag, selected signal kind, and Leg2-to-H5 offset
- [x] 2.2 Preserve compatibility with older sessions that do not contain Leg2 datasource fields
- [x] 2.3 Add a Leg2 `.mat` startup argument for the heatmap alignment GUI
- [x] 2.4 Implement startup/session precedence so an explicit startup `.mat` replaces any Leg2 datasource stored in a loaded session
- [x] 2.5 Add tests for session round-trip, older-session defaults, missing stored `.mat` reload handling, and startup override behavior

## 3. Timeline Integration

- [x] 3.1 Extend the timeline state/range model to include an optional Leg2 track duration and Leg2-to-H5 offset without coupling it to the camera offset
- [x] 3.2 Render a distinct colored Leg2 `.mat` timeline row when the datasource is loaded
- [x] 3.3 Make the Leg2 timeline row draggable using the same offset sign convention and off-screen drag behavior as the camera row, refreshing dependent views on release
- [x] 3.4 Ensure dragging the Leg2 row changes only the Leg2 offset and dragging the camera row changes only the camera offset
- [x] 3.5 Display the current Leg2 offset or aligned track start value somewhere visible in the interface when the Leg2 datasource is loaded
- [x] 3.6 Add tests for timeline bounds, offset sign convention, independent camera/Leg2 dragging, and timeline-to-Signals pixel alignment with the Leg2 track visible
- [x] 3.7 Move offset labels into the Timeline row for offset-bearing tracks, positioned just left of each track bar with edge clipping/hiding behavior

## 4. Signals Plot Integration

- [x] 4.1 Generalize the Signals plot data path enough to render the existing H5 peak-distance signal and one selected Leg2 ultrasonic signal together
- [x] 4.2 Add a raw/filtered Leg2 ultrasonic selector that shows only one Leg2 ultrasonic signal at a time
- [x] 4.3 Plot Leg2 ultrasonic data in aligned shared timeline coordinates using the Leg2 offset
- [x] 4.4 Use a readable Leg2 plot color derived from the Leg2 timeline track color
- [x] 4.5 Segment the plotted Leg2 signal into slightly transparent primary samples where `DataRecordCommon.ReliableFlag` is true and lower-alpha samples where `DataRecordCommon.ReliableFlag` is false
- [x] 4.6 Preserve missing-value gaps in Leg2 ultrasonic plots
- [x] 4.7 Update the compact legend to identify the selected Leg2 ultrasonic signal as raw or filtered, with `(valid)` / `(not valid)` Leg2 segment labels
- [x] 4.8 Add tests for signal selection, `ReliableFlag`-based segmentation, missing-value gaps, legend entries, and x-axis alignment in Timeline mode
- [x] 4.9 Ensure all segmented Signals plot series visually bridge primary/faded transitions while preserving true missing-value gaps, and add focused tests

## 5. GUI Resource Actions

- [x] 5.1 Add interactive load and clear actions for the Leg2 `.mat` datasource
- [x] 5.2 Report Leg2 `.mat` load failures with clear user-facing messages that include the missing or invalid field context
- [x] 5.3 Keep camera video, H5 heatmap, and H5 peak-distance datasource state unchanged when loading, clearing, or failing to load a Leg2 `.mat`
- [x] 5.4 Keep synced video export behavior and duration unchanged when a Leg2 ultrasonic datasource is loaded

## 6. Verification

- [x] 6.1 Run focused tests with the repo-managed Hatch environment for heatmap alignment core and GUI behavior
- [x] 6.2 Manually smoke-test loading a representative Leg2 `.mat`, switching raw/filtered display, dragging the Leg2 track (direction verified), saving/loading a session, and launching with the `.mat` startup argument
- [x] 6.3 Run `openspec validate add-leg2-mat-ultrasonic-datasource --strict`
