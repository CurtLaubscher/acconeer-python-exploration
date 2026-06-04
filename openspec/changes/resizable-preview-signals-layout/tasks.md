## 1. Layout Implementation

- [x] 1.1 Refactor the main workbench layout so Preview and Signals are children of a vertical `QSplitter`, with Timeline remaining outside the splitter as a fixed-height area
- [x] 1.2 Keep the existing horizontal Preview splitter nested inside the Preview pane and preserve its current camera/right-preview stretch behavior
- [x] 1.3 Set practical minimum sizes and non-collapsible splitter behavior so Preview and Signals remain usable after resizing
- [x] 1.4 Confirm no splitter positions are persisted or written to alignment session JSON
- [x] 1.5 Prevent the vertical splitter from shrinking the Preview area into viewport/rendered-heatmap control overlap

## 2. Verification

- [x] 2.1 Add or update focused GUI tests for the Preview/Signals splitter structure if the existing Qt test harness supports it cleanly
- [x] 2.2 Manually launch the workbench with the repo-defined Hatch app command and verify Preview/Signals resizing, fixed Timeline height, and preserved horizontal Preview resizing
- [x] 2.3 Check a small-window layout manually and tune implementation-only default stretch/minimum values without adding hard-coded sizing requirements to the OpenSpec docs
- [x] 2.4 Verify a reduced Preview allocation clamps before viewport/rendered-heatmap controls overlap preview content
