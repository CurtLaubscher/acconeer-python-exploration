## Why

Radar heatmap recordings need to be aligned with tripod camera videos that include the same heatmap displayed on a monitor. A GUI-based alignment workbench will make it practical to manually define the camera viewport, compare it against a ground-truth heatmap rendered from H5 data, and save reusable alignment artifacts for multiple videos recorded from the same setup.

## What Changes

- Add a standalone PySide6 utility under `user_tools/` for aligning one camera video track with one H5-rendered Sparse IQ heatmap track.
- Render the ground-truth heatmap directly from raw H5 values using the same distance/velocity heatmap logic as `user_tools/export_sparse_iq_heatmap_video.py`.
- Provide an interactive camera view where the user can drag four fixed viewport corners over the heatmap body visible in the camera video.
- Show the rectified camera viewport and rendered heatmap at identical pixel size and aspect ratio so they are directly comparable.
- Provide physical-seconds timeline controls for scrubbing, manual offset adjustment, playback preview without MVP audio support, and fine temporal nudging.
- Display a cross-correlation diagnostic plot between the rectified camera viewport and rendered heatmap without using it for automatic alignment in the MVP.
- Provide save/load support for alignment artifacts containing source paths, viewport geometry, H5 selection, render/color settings, timeline offset, and preprocessing settings.

## Capabilities

### New Capabilities

- `heatmap-alignment-gui`: Interactive alignment of a tripod camera video to an H5-rendered Sparse IQ heatmap on a shared physical timeline.

### Modified Capabilities

- None.

## Impact

- Adds a new standalone user tool in `user_tools/`.
- Refactors shared heatmap rendering logic out of `user_tools/export_sparse_iq_heatmap_video.py` if needed to avoid duplicated rendering behavior.
- Requires OpenCV-compatible video frame extraction and perspective warping for the GUI alignment workflow.
- Uses existing PySide6 GUI dependencies already present in the project.
- Introduces JSON alignment artifacts that future export and auto-refinement tools can consume.
