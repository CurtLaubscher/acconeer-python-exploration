# Heatmap Alignment GUI Ideas

This is a living idea list for the heatmap alignment workbench. Items here are not accepted scope and are not implementation commitments. Promote an idea into a new OpenSpec change when it becomes concrete enough to build.

## Context For Future Agents

The current MVP is accepted and archived. The durable behavior contract is `openspec/specs/heatmap-alignment-gui/spec.md`; this file is only a parking lot for ideas. Do not treat any item here as approved scope without first proposing a new OpenSpec change.

Current architecture notes:
- The GUI is a PySide6 tool in `user_tools/heatmap_alignment_gui.py`.
- Core session/video/heatmap logic lives in `user_tools/heatmap_alignment_core.py`.
- Shared Sparse IQ heatmap rendering helpers live in `user_tools/sparse_iq_heatmap_common.py`.
- The GUI uses a disposable local preview proxy for responsive camera playback, while sessions store the original camera video path.
- Viewport geometry is now intended to be stored in original camera video coordinates; preview/proxy drawing maps it into display coordinates.
- The viewport preview has a source-resolution paused render path: after interaction settles, the app can warp from the original camera frame into the current viewport preview size.
- Export reopens the original-resolution camera video and composites a plotted H5 heatmap overlay into the scaled export rectangle.
- Xcorr prototype code exists, but GUI xcorr is intentionally disabled for MVP due to performance and reliability concerns.

Current priority signals:
- Basic viewport visibility transforms and source-resolution paused preview have been implemented, but the color match still does not feel right enough to call the enhancement algorithm solved.
- A focused color-matching improvement is likely the next alignment-aid candidate if manual comparison remains difficult.
- Export dialog settings and overlay plot formatting are plausible near-term changes because export is already useful and the output styling can be improved incrementally.
- Background/async processing is attractive but not urgent for the current workflow of manually processing about 5-10 trials.
- Batch workflows are intentionally not prioritized because each trial still needs manual review.
- PyAV/FFmpeg, GPU decode, RAM caching, and xcorr should be driven by concrete measurements or pain points rather than assumed wins.

Useful implementation posture:
- Keep manual alignment as the authority unless a future feature explicitly asks the user to accept an automated suggestion.
- Prefer small, measured changes over architecture rewrites.
- Preserve the simple one-camera/one-H5 workflow even if future abstractions support more sources.
- Avoid putting raw brainstorm items into the accepted spec; use this file for ideas and OpenSpec changes for committed work.
- When delegating implementation to another agent, include direct links/paths to the relevant OpenSpec proposal, design, spec, tasks, and this ideas file in addition to conversational context.

## Likely Next Candidates

### Viewport color matching

Manual alignment can be difficult because the camera-captured monitor colors are sometimes hard to interpret after rectification. The first viewport enhancement pass provides low/high/gamma correction plus optional luminance-to-viridis mapping, but live use suggests that this is not enough to make the captured viewport closely resemble the rendered H5 heatmap.

Possible directions:
- Auto levels for the rectified viewport, probably percentile-based, as a quick starting point for low/high values.
- Palette matching using an optimized 3D lookup table that maps camera RGB to nearest viridis colors.
- Flicker comparison between the rectified viewport and rendered H5 heatmap in the same panel.
- Sample-based calibration where the user marks low/background, mid, and high colors from the camera-captured heatmap.
- Better preset defaults for the existing low/high/gamma controls.
- Keep raw/enhanced toggling fast so transforms remain a comparison aid rather than hidden truth.

This is a likely prerequisite before investing more time in xcorr, because xcorr quality depends on making the camera-derived viewport more comparable to rendered truth.

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
- The GUI preview should match the exported result closely enough that users can trust it before spending time on export.

Possible directions:
- Use a consistent style function for preview and export.
- Scale fonts based on overlay pixel size.
- Add compact and full plot presets.
- Add user-editable overlay plot styling for font sizes, tick styling, margins/padding, and related readability settings.
- Add optional colorbar support.
- Tune margins with fixed minimums so labels do not get clipped.
- Re-render the overlay heatmap while the user drags to resize the export overlay, possibly throttled or lower quality if needed.
- Add preview/export visual parity checks for plot layout, font sizing, axes, and colorbar behavior.

### Timeline polish

The current timeline is intentionally compact and focused, but future polish could make temporal alignment easier and less ambiguous.

Possible directions:
- Add horizontal zoom and pan for longer recordings.
- Add `Fit All` and `Fit Overlap` actions.
- Add optional overlap shading if users still find the two-track relationship confusing.
- Improve tick density and labels as zoom changes.
- Preserve the simple H5-fixed, camera-draggable model unless a broader timeline model is explicitly needed.

## Useful But Lower Priority

### Background and async processing

Move long-running work off the main GUI path so the app remains interactive.

Possible directions:
- Load camera/H5 files without freezing the UI, especially for longer trials.
- Show loading progress or a clear busy state when file probing, H5 loading, or proxy preparation takes noticeable time.
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

### Session launch shortcuts

Make it faster to resume a saved alignment session directly from the command line.

Possible directions:
- Add a CLI argument for launching the workbench with an existing session JSON file.
- Restore the saved session after startup using the same load behavior as the GUI session picker.
- Keep existing camera/H5 startup arguments working for new sessions.
- Define precedence clearly if both a session file and individual source paths are provided.

### Export robustness

Improve export behavior around unusual files, failures, and partial outputs.

Possible directions:
- Keep deleting partial output files on failure or cancellation.
- Make export failure messages more specific when camera decode, H5 render, or video writer setup fails.
- Add focused handling for camera files with unreadable trailing frames or inconsistent reported frame counts.
- Add export smoke tests using synthetic videos with known bad/missing frames.
- Keep codec-specific work measurement-driven rather than switching decode/export stacks speculatively.

### Source-resolution viewport processing

The current paused source-resolution viewport preview is a single-frame, latest-request-wins path. Future work could make this more proactive or cached if needed.

Possible directions:
- Pre-warp original-resolution camera footage into a source-resolution viewport proxy.
- Cache recently requested source-resolution viewport frames.
- Render nearby paused frames after the user stops scrubbing or dragging.
- Keep low-quality frames available immediately as the fallback interaction path.

This is related to async processing, but specifically targets viewport visual quality and not just responsiveness.

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

### Source-coordinate geometry follow-ups

Viewport geometry has moved toward original camera coordinates. Remaining geometry questions are mostly about consistency and future export/overlay behavior.

Possible directions:
- Decide whether export overlay geometry should remain preview-space or move to source/normalized coordinates.
- Store source dimensions explicitly in the session if future compatibility needs it.
- Consider normalized geometry if sessions need to survive source video transcoding/resizing.
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
