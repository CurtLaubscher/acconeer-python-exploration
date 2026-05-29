## Context

The heatmap alignment GUI uses H5 elapsed time as the shared timeline origin. Camera and Leg2 tracks store offsets relative to H5, and the H5 bar is drawn at shared time zero. The Timeline widget already supports dragging camera and Leg2 bars and dragging the current-time marker, but mouse press handling checks track bars before the playhead, so a click on the current-time marker can accidentally move the bar underneath it.

The longer-term model should not treat H5 as permanent ground truth. That broader global-reference timeline would give H5 its own offset and make all tracks peers, but it would touch session schema, frame lookup, signal plotting, export assumptions, and existing offset controls. This change intentionally keeps the current persisted H5-as-origin model while making the H5 bar usable as a short-term relative-drag handle.

## Goals / Non-Goals

**Goals:**

- Make Timeline current-time marker clicks and drags win over overlapping track bars.
- Let users drag the H5 bar in a way that feels like moving the H5 block itself.
- Preserve the current saved-session schema and H5-at-zero coordinate model.
- Shift all loaded non-H5 offset-bearing tracks as needed when the user drags H5 so the relative alignment changes consistently.
- Keep the playhead's screen-relative position stable during H5 drag by updating current time and visible x-limits as part of the gesture.
- Document the future H5-own-offset/global-reference model in the heatmap alignment ideas file.

**Non-Goals:**

- Add a persisted H5 offset.
- Migrate alignment session JSON.
- Redesign the camera offset spinbox or nudge buttons into generic selected-track controls.
- Add timeline zoom, pan, track selection, linked-track groups, or track pinning.
- Change synced video export duration or H5 frame lookup semantics.

## Decisions

### Prioritize playhead hit testing before track hit testing

Timeline mouse press handling should check the current-time marker hit area before camera, H5, or Leg2 track rectangles. This matches the existing hover affordance and makes the object that looks active become the object that receives the drag.

Alternative considered: increase the playhead visual width or move the playhead above bars only visually. That would not fix the actual press dispatch bug and could make track dragging harder.

### Model H5 drag as a coordinate-frame drag

Because H5 still has no stored offset, dragging H5 should adjust the temporary coordinate frame rather than persisting an H5 position. The observable behavior should match grabbing the H5 block: the H5 bar follows the pointer, the playhead keeps its screen-relative position during the gesture, and loaded non-H5 offset-bearing tracks preserve their screen-relative positions while their stored offsets are updated to reflect the new relative alignment. The implementation can choose the necessary sign conventions for x-range, current-time, and offset updates as long as this UX contract holds.

After the gesture, the persisted state still describes all alignment relative to H5, and H5 remains stored at shared time zero.

Alternative considered: only update camera and Leg2 offsets. That changes relative alignment but makes the H5 bar feel pinned to the viewport instead of behaving like the grabbed object.

Alternative considered: introduce a real H5 offset now. That is the cleaner destination model, but it is a larger data-model change than this refinement needs.

### Shift all loaded non-H5 offset-bearing tracks

The H5 drag should apply to every loaded track that already owns an offset relative to H5, not just Camera. Today that includes Camera and Leg2. H5-derived peak-distance JSON should remain coupled to H5 because it is derived from the radar recording rather than being an independent offset-bearing source.

Alternative considered: shift only the camera offset because the visible camera offset controls already exist. That would make H5 dragging inconsistent in sessions that also load Leg2.

### Make H5-only drag a no-op

If H5 is the only loaded timeline resource, H5 dragging should do nothing in this short-term model. There are no non-H5 offsets to adjust, and there is no stored H5 offset to persist. The ideas document should call this out as a limitation that should disappear when the timeline moves to a global reference model.

Alternative considered: allow H5-only drag to move current time and x-limits only. That would feel like a hidden pan/scrub gesture rather than an alignment change and could be confusing while the Timeline has no explicit pan mode.

## Risks / Trade-offs

- [Temporary model may confuse future maintainers] -> Keep code and docs clear that H5 dragging is a bridge behavior, not a real H5 offset.
- [Current-time shifting during H5 drag can surprise users] -> Preserve the playhead's screen-relative position so the gesture visually explains the time change.
- [Signals plot and Timeline x mapping can drift] -> Update timeline range, current time, and offsets through the same refresh path that already synchronizes Timeline and Signals geometry.
- [H5-only no-op can feel broken] -> Only show draggable affordance or start an H5 drag when at least one non-H5 offset-bearing track is loaded.
