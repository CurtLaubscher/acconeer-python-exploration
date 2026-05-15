# Heatmap Alignment GUI Ideas

This is a living idea list for the heatmap alignment workbench. Items here are not accepted scope and are not implementation commitments. Promote an idea into a new OpenSpec change when it becomes concrete enough to build.

## Context For Future Agents

The current MVP is accepted and archived. The durable behavior contract is `openspec/specs/heatmap-alignment-gui/spec.md`; this file is only a parking lot for ideas. Do not treat any item here as approved scope without first proposing a new OpenSpec change.

Current architecture notes:
- The GUI is a PySide6 tool in `user_tools/heatmap_alignment_gui.py`.
- Core session/video/heatmap logic lives in `user_tools/heatmap_alignment_core.py`.
- Shared Sparse IQ heatmap rendering helpers live in `user_tools/sparse_iq_heatmap_common.py`.
- The GUI uses a disposable local preview proxy for responsive camera playback, while sessions store the original camera video path.
- Preview geometry is currently stored in preview-space coordinates.
- Export reopens the original-resolution camera video and composites a plotted H5 heatmap overlay into the scaled export rectangle.
- Xcorr prototype code exists, but GUI xcorr is intentionally disabled for MVP due to performance and reliability concerns.

Current priority signals:
- Viewport visibility transforms are likely the most useful next alignment aid because manual spatial/temporal alignment was made harder by low-contrast camera-captured heatmap colors.
- Export dialog settings and overlay plot formatting are plausible near-term changes because export is already useful and the output styling can be improved incrementally.
- Background/async processing is attractive but not urgent for the current workflow of manually processing about 5-10 trials.
- Batch workflows are intentionally not prioritized because each trial still needs manual review.
- PyAV/FFmpeg, GPU decode, RAM caching, and xcorr should be driven by concrete measurements or pain points rather than assumed wins.

Useful implementation posture:
- Keep manual alignment as the authority unless a future feature explicitly asks the user to accept an automated suggestion.
- Prefer small, measured changes over architecture rewrites.
- Preserve the simple one-camera/one-H5 workflow even if future abstractions support more sources.
- Avoid putting raw brainstorm items into the accepted spec; use this file for ideas and OpenSpec changes for committed work.

## Likely Next Candidates

### Viewport visibility transforms

Manual alignment can be difficult because the camera-captured monitor colors are sometimes hard to interpret after rectification. Add preview transforms that make the warped viewport easier to compare against the rendered H5 heatmap.

Possible directions:
- Contrast/gamma adjustment for the rectified viewport.
- Grayscale or luminance-only view.
- Edge-emphasis view.
- Colormap-like remapping to make low-contrast heatmap structure easier to see.
- Side-by-side or toggleable comparison modes that preserve the current raw view.

This is a likely prerequisite before investing more time in xcorr, because xcorr quality depends on making the camera-derived viewport more comparable to the rendered truth.

### Export dialog settings

Add an export options dialog before writing the synced video.

Possible settings:
- Output resolution: original camera resolution, preview resolution, or custom scale.
- Encoder quality/bitrate.
- Output FPS policy: max source FPS, camera FPS, H5 FPS, or custom FPS.
- Overlay opacity.
- Include or hide axes.
- Include or hide colorbar.
- Reuse current output path defaults from the session/source paths.

### Overlay plot formatting

Improve the plotted heatmap overlay used in preview and export.

Known issues:
- Font sizing can differ noticeably between preview and exported video.
- Whitespace around axes can be tightened.
- Label density and tick formatting may need tuning for small overlays.
- The default lower-left overlay may need styling presets for readability.

Possible directions:
- Use a consistent style function for preview and export.
- Scale fonts based on overlay pixel size.
- Add compact and full plot presets.
- Add optional colorbar support.
- Tune margins with fixed minimums so labels do not get clipped.

## Useful But Lower Priority

### Background and async processing

Move long-running work off the main GUI path so the app remains interactive.

Possible directions:
- Load camera/H5 files without freezing the UI.
- Export while the user can continue reviewing or preparing another session.
- Generate or rebuild proxy videos in the background.
- Decode likely-nearby frames around the current time in the background.
- Render higher-quality paused previews after interaction settles.
- Use a configurable RAM budget to decide how much decoded preview/full-res data to keep.

This is attractive architecturally, but not critical for the current small manual trial count.

### Proxy/cache management

Make the disposable preview proxy system more visible and controllable.

Possible directions:
- Show proxy build/reuse status more explicitly.
- Provide a rebuild proxy action.
- Provide a clear proxy cache action.
- Surface cache location and approximate cache size.
- Track proxy generation errors in a user-visible way.

### High-quality background viewport processing

Precompute expensive high-quality derived video data while the user works.

Possible directions:
- Pre-warp original-resolution camera footage into a high-quality viewport proxy.
- Replace low-quality viewport preview with high-quality frames when ready.
- Render high-quality paused frames after the user stops scrubbing or dragging.
- Keep low-quality frames available immediately as the fallback interaction path.

This is related to async processing, but specifically targets high-quality preview and not just responsiveness.

## Alignment Assistance

### Temporal xcorr diagnostic

Reintroduce xcorr as a background diagnostic for exact time alignment.

Notes:
- Do not auto-apply xcorr offsets without explicit user action.
- Run it in the background so loading and manual preview remain responsive.
- Revisit only after viewport visibility transforms make the camera-derived heatmap more comparable to rendered truth.
- Keep manual alignment as the source of truth.

### Spatial alignment assistance

Explore whether the tool can help refine viewport geometry automatically.

Possible directions:
- Image registration over the rectified viewport.
- Corner optimization against a similarity score.
- Edge/structure-based alignment aids.
- Local search around the user's current quadrilateral.

This is likely harder and more fragile than temporal xcorr. It should be treated as exploratory unless a concrete failure case motivates it.

### Moving-camera or time-varying viewport geometry

Support viewport corners that change over time.

Possible directions:
- Add viewport keyframes on the timeline.
- Interpolate quadrilateral corners between keyframes.
- Show keyframe markers in the timeline.
- Keep the current single fixed quadrilateral as the default simple case.

This matters if camera/monitor movement becomes a real problem. It is not a current priority.

## Architecture And Data Model

### Internal session naming cleanup

The user-facing UI now says "Session", but some internal code still uses "artifact" names. A dedicated cleanup could rename internal functions/classes/constants where practical.

Considerations:
- Keep backward compatibility with existing saved JSON.
- Avoid schema churn unless there is a concrete reason.
- The existing `AlignmentSession` dataclass already uses the right conceptual name.

### Source-coordinate geometry

The MVP stores viewport and export overlay geometry in preview-space coordinates. Future higher-quality workflows may benefit from storing source-coordinate geometry too.

Possible directions:
- Store both preview and source dimensions in the session.
- Store geometry normalized to source dimensions.
- Add migration logic for existing sessions.
- Keep proxy files disposable and excluded from session state.

### More general data source framework

The current implementation is conceptually track-based but practically hard-coded for one camera video and one H5 heatmap source.

Possible future directions:
- Add pluggable source adapters for additional data formats.
- Allow additional video-like or signal-like tracks.
- Preserve the simple two-track workflow as the default.

This is not needed for current H5/camera workflows, but it may matter if future data sources need alignment.

## Decoder And Export Experiments

### PyAV or FFmpeg decode/export experiments

OpenCV is currently adequate and remains useful for frame operations such as warping. PyAV/FFmpeg may be worth revisiting only with a measured bottleneck or codec limitation.

Possible areas to test:
- More robust handling of unusual camera files.
- Better control over seeking and keyframes.
- Hardware decode paths.
- Encoding quality and codec options.
- Piping decoded frames into OpenCV only for operations OpenCV handles well.

Earlier testing did not show an obvious win from OpenCV hardware acceleration, likely because frames still need to return to CPU memory for Qt/OpenCV processing.

### Full or partial decoded RAM cache

Allow the app to decode and cache more footage when enough RAM is available.

Possible directions:
- User-configurable memory budget.
- Cache nearby frames around current time.
- Cache full clips when they fit within the budget.
- Prefer low-resolution decoded cache first, then optional original-resolution cache.

This could improve responsiveness and higher-quality preview, but it should be guided by measured memory and decode behavior.
