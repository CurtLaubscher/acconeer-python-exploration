## Why

Manual alignment can now compare H5 peak distance over time against the shared timeline, but Leg2 ultrasonic measurements remain outside the heatmap alignment workflow. Loading the Leg2 `.mat` log directly into the workbench would let the user visually align radar, camera, and prosthesis ultrasonic data in one place.

## What Changes

- Add Leg2 `.mat` import as an optional datasource in the heatmap alignment GUI.
- Extract hard-coded Leg2 ultrasonic arrays from the expected exported structure:
  - time from `DataRecordCommon.timeOut`
  - raw ultrasonic distance from `Ultrasonic.Distance`
  - filtered ultrasonic distance from `DataRecordCommon.ultrasonic_filtered`
  - reliable ultrasonic-use segmentation from `DataRecordCommon.ReliableFlag`
- Convert ultrasonic distance values to meters before plotting.
- Ignore erroneous trailing `timeOut == 0` samples after valid time samples.
- Display the Leg2 `.mat` as its own colored timeline track with its own draggable offset relative to the H5 reference, behaving like the draggable camera/video track.
- Plot one selected ultrasonic signal at a time in the existing Signals area, with a raw/filtered toggle, samples where `DataRecordCommon.ReliableFlag` is true rendered as a slightly transparent primary color, and other samples rendered lower alpha.
- Add startup, session, and artifact persistence for the loaded Leg2 `.mat` datasource, selected ultrasonic signal, visibility, and offset.
- Add interactive load and unload controls for Leg2 `.mat` files, similar to the existing Peak-Distance JSON controls.
- Hard-fail `.mat` loads with clear user-facing errors when required fields are missing, invalid, non-monotonic after cleanup, or length-incompatible.
- Keep this change manual-only: no xcorr, no automated offset suggestion, no generic `.mat` variable browser, no new synced-video export behavior, and no dedicated offset nudge/spin controls for the `.mat` track.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `heatmap-alignment-gui`: Add Leg2 `.mat` ultrasonic datasource import, timeline-track alignment, Signals plot display, startup/session persistence, and load validation behavior.

## Impact

- Affected GUI/core code:
  - `user_tools/heatmap_alignment_gui.py`
  - `user_tools/heatmap_alignment_core.py`
  - any existing heatmap alignment CLI entry point or argument parsing in the same tool
- Affected persistence:
  - Alignment session JSON schema gains optional Leg2 `.mat` datasource state while older sessions remain valid.
- Dependencies:
  - Expected to use existing repo-managed scientific Python dependencies for MATLAB v5 `.mat` loading; update `pyproject.toml` only if the chosen implementation requires a dependency not already provided by the Hatch app environment.
- Tests:
  - Add focused core tests for `.mat` extraction/validation, time cleanup, unit conversion, signal segmentation, timeline/session persistence, and startup/session precedence.
