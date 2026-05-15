## Context

The heatmap alignment workbench currently rectifies the selected camera viewport and shows it next to the rendered H5 heatmap. In real trial usage, the camera-captured monitor heatmap can be hard to read because camera exposure, monitor brightness, glare, compression, and color response make the viewport visually different from the rendered truth.

This change adds lightweight viewport visibility transforms for manual comparison. It does not reintroduce xcorr. The goal is to make the human alignment task easier and to establish a better visual preprocessing path if xcorr is revisited later.

## Goals / Non-Goals

**Goals:**

- Provide a simple raw/enhanced toggle for the rectified viewport preview.
- Make low-contrast camera-captured heatmap structure easier to see.
- Keep the raw viewport view available.
- Persist enhancement enabled state and tuning values in alignment sessions.
- Keep transforms fast enough for scrubbing and playback preview.

**Non-Goals:**

- Automatically aligning time or geometry.
- Re-enabling xcorr in this change.
- Changing exported synced video behavior.
- Changing the rendered H5 truth heatmap color controls.
- Adding grayscale or edge modes in the first implementation.
- Adding a broad image-processing workbench with many advanced controls.

## Decisions

### Use a single enhancement toggle instead of transform modes

The UI should expose one primary `Enhance Viewport` toggle. When disabled, the viewport preview uses the raw rectified camera frame and the enhancement tuning controls are disabled. When enabled, the viewport preview uses the current enhancement settings.

This makes raw/enhanced comparison quick and keeps the mental model simpler than mutually exclusive modes. The user can tune one enhanced view and temporarily disable it without losing the chosen tuning values.

Alternatives considered: a mode selector with raw, contrast, grayscale, and edge views would be flexible but less directly tied to the real goal of making the viewport resemble the rendered viridis heatmap. Edge and grayscale modes may still be useful later, but they are not the first implementation target.

### Tune luminance first, then optionally map to viridis

The enhanced view should first apply low/high/gamma correction to the viewport image. The corrected image should preserve the original viewport colors when viridis mapping is disabled. When `Map to Viridis` is enabled, the implementation should compute corrected luminance and use that 1D scalar to look up viridis RGB values.

Initial tuning:

- `Low`: lower range handle for viewport intensity correction.
- `High`: upper range handle for viewport intensity correction.
- `Gamma`: curve control for viewport intensity correction.
- `Map to Viridis`: optional toggle that displays corrected luminance through the viridis ramp.

The conceptual transform is:

```text
corrected_rgb = clamp((camera_rgb - low) / (high - low), 0, 1) ** gamma
if map_to_viridis:
    scalar = luminance(corrected_rgb)
    enhanced_rgb = viridis(scalar)
else:
    enhanced_rgb = corrected_rgb
```

The low/high controls should be draggable range handles rather than typed-only numeric fields, because the user is tuning by eye during alignment.

Alternatives considered: nearest-color inverse projection onto the viridis ramp is conceptually direct but was measured to be far too slow when implemented per pixel. A cached 3D color lookup table would be faster, but a luminance-first 1D transform is simpler, much cheaper, and closer to the user's intent of correcting intensity before optional palette mapping. Inverse colormap recovery can still be revisited later if real data shows luminance mapping is insufficient.

### Place viewport controls near the viewport preview

Viewport enhancement controls should be visually associated with the `Viewport` preview rather than mixed into rendered heatmap color controls. This reduces ambiguity: the controls affect the rectified camera viewport only, not the camera source view, rendered H5 heatmap, or synced video export overlay.

Alternatives considered: keeping controls in the existing `Render` group is simpler, but that group already mixes H5 color limits, disabled xcorr/preprocess controls, and preview-related settings.

### Apply transforms only to the rectified viewport preview

Transforms should operate after rectification, on the viewport preview frame, not on the source camera view. The source camera remains the place for geometry editing, while the viewport preview is the place for visual comparison.

Alternatives considered: transforming the camera source view would make geometry handles harder to interpret and would conflate source inspection with comparison rendering.

### Persist settings in the alignment session

The enhancement enabled state and tuning values should be saved with the session so reloading a session reproduces the same comparison view. Existing sessions should load with defaults equivalent to current raw behavior.

Alternatives considered: keeping transforms as UI-only state would be simpler but would make saved alignment work less reproducible.

### Keep implementation local and dependency-free

Transforms should use NumPy and OpenCV, which are already used by the workbench. The transform helper should live in `heatmap_alignment_core.py` so it can be unit tested independently of Qt.

Alternatives considered: using Matplotlib or PIL for transforms would add overhead and duplicate existing OpenCV image-processing capabilities.

## Risks / Trade-offs

- Too many controls could slow manual alignment -> use one enhance toggle, draggable low/high range handles, and one gamma control.
- Transformed previews may mislead users if they hide raw camera artifacts -> make raw/enhanced toggling immediate and visible.
- Viridis mapping from luminance may be imperfect under monitor/camera color shifts -> treat it as a manual visibility aid, not truth reconstruction.
- Transform processing could affect playback smoothness -> keep transforms lightweight and measure if live playback becomes uneven.
- Session schema changes can affect old files -> provide defaults when `viewport_visibility` is absent.
