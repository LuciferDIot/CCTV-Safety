# Comprehensive Monorepo Audit Report: CCTV-Safety

**Date**: 2026-11-08  
**Integrity Mode**: Development  
**Auditors**: Teamwork Explorer Agents (Backend Auditor, Frontend Auditor, Notebook & Pipeline Auditor)  
**Status**: Monorepo Audit Complete — Documented Prior to Remediation (R1 Requirement)

---

## Executive Summary

A comprehensive multi-agent audit was conducted across the entire CCTV-Safety monorepo, covering:
1. **Backend Subsystem (`backend/`)**: FastAPI application, MVC + Services architecture, LOC compliance (<= 100 LOC), test suite execution, and bug inspection.
2. **Frontend Subsystem (`frontend/`)**: Next.js 16 application, Brad Frost Atomic Design compliance, build verification, runtime stability, and UI state integrity.
3. **Notebook & Evaluation Pipeline (`backend/notebooks/cctv_safety_pipeline.ipynb`)**: Ground truth benchmark evaluation against `data/eval_gt.json`, accuracy metrics (Precision, Recall, F1), execution speed benchmarks, cell outputs, and failure modes.

### Critical Summary Table
| Area | Status | Critical Violations & Bugs | LOC / Build Status |
|---|---|---|---|
| **Backend** | Remediate Required | 3 files violate <= 100 LOC; Fatal `AttributeError` on pedestrian detection; Pipeline discards video/event output; In-memory zone overrides lost on reload; Path traversal vulnerabilities; Memory leaks. | 40/43 files pass LOC; 3 files violate LOC (111, 107, 103). 12/12 tests pass in `backend/tests/`. |
| **Frontend** | Remediate Required | P0 Fatal Runtime Crash on event load due to backend-frontend DTO contract mismatch; Brad Frost Atomic Design violations (`components/ui/button.tsx`, inlined status dots/buttons); Missing zone persistence (`saveZones` never invoked); Coordinate clamping bug (4200x2200 vs 3840x2160); Full video pipeline truncation. | Next.js 16.4.3 build passes (`pnpm build`). Needs removal of `typescript.ignoreBuildErrors`. |
| **Notebook & Eval Pipeline** | Remediate Required | Broken imports (`ModuleNotFoundError: pandas` in Cells 58 & 64); Unexecuted Cells 58 & 64; Duplicate section 11 numbering; Disconnected benchmark horizon (20 GT events span 109s vs 22.9s video); Algorithmic false positives (48 FP from missing crosswalk flow suppression & loose lane auto-detection); CPU speed reality (~2.0 FPS vs claimed 28.5 FPS). | 69 cells; evaluation against `data/eval_gt.json` yielded Overall F1: 0.143 (filtered) / 0.111 (unfiltered). |

---

## 1. Backend Subsystem Audit

### 1.1 LOC Compliance (Strict <= 100 LOC Constraint)
Line count analysis for all 43 Python files in `backend/`:
- **Compliant files**: 40 / 43 (93.0%)
- **Violating files**: 3 / 43 (7.0%)
  1. `backend/services/cv/annotator.py`: **111 LOC** (+11 lines over limit)
  2. `backend/services/cv/tracker.py`: **107 LOC** (+7 lines over limit)
  3. `backend/services/safety/crosswalk.py`: **103 LOC** (+3 lines over limit)
- **High-Risk Files Near Limit (90–99 LOC)**:
  - `backend/services/safety/clustering.py`: 99 LOC
  - `backend/services/safety/direction.py`: 99 LOC
  - `backend/services/pipeline_service.py`: 98 LOC
  - `backend/services/event_service.py`: 93 LOC

### 1.2 Architectural Compliance: Flat MVC + Services
The backend adheres to the required flat MVC + Services layout:
- `controllers/`: HTTP route handlers (`event_controller.py`, `health_controller.py`, `pipeline_controller.py`, `router.py`, `video_controller.py`, `zone_controller.py`, `deps.py`).
- `models/`: Domain business entities (`event.py`, `track.py`, `zone.py`).
- `views/`: Pydantic validation schemas & DTOs (`event_views.py`, `pipeline_views.py`, `video_views.py`, `zone_views.py`).
- `services/`: Core application services (`event_service.py`, `pipeline_service.py`, `video_service.py`, `zone_service.py`, `event_demo.py`).
- `services/cv/`: Computer vision subsystem (`annotator.py`, `engine.py`, `hud.py`, `model.py`, `tracker.py`).
- `services/safety/`: Safety analysis rules (`clustering.py`, `crosswalk.py`, `direction.py`, `fusion.py`, `geometry.py`, `pedestrian.py`, `vehicles.py`).
- `config.py`: Configuration singleton.
- `main.py`: Application entrypoint.

No nested sub-controllers or nested sub-models exist. Dependency flow is strictly unidirectional (`controllers -> services -> models/views`).

### 1.3 Test Suite Execution
- **Command**: `.venv\Scripts\python.exe -m pytest backend/tests -v`
- **Results**: **12 passed, 1 warning (100% passing in 3.25s)**
- **Coverage**:
  - `test_root_and_health`: PASS
  - `test_videos_endpoints`: PASS
  - `test_zones_crud`: PASS
  - `test_events_filtering`: PASS
  - `test_pipeline_telemetry_and_cancel`: PASS
  - `test_pipeline_start_and_status`: PASS
  - `test_demo_scenarios_presence`: PASS
  - `test_csv_export_format`: PASS
  - `test_direction_checker_alignment`: PASS
  - `test_vehicle_type_classification`: PASS
  - `test_crosswalk_motion_rules`: PASS
  - `test_kmeans_lane_auto_clustering`: PASS

### 1.4 Detailed Backend Bugs & Defects
1. **Fatal RuntimeError on Pedestrian Detection**: In `backend/services/cv/engine.py:70`, `self.ann.zone_annotators` (instances of `TranslucentZoneAnnotator`) are passed to `self.pedestrian_checker.check_safety(...)`. Inside `pedestrian.py:26`, it calls `l_zone.trigger(detections=persons)`. `TranslucentZoneAnnotator` has no `trigger()` method, throwing `AttributeError: 'TranslucentZoneAnnotator' object has no attribute 'trigger'`.
2. **Pipeline Video Output & Event Persistence Discarded**: In `backend/services/pipeline_service.py:84`, processed frames are discarded without being written to disk via `cv2.VideoWriter`. Furthermore, detected events are not accumulated or written to `data/output/detected_events.json`, and `task["events_detected"]` remains 0.
3. **In-Memory Zone Overrides Lost Between Requests**: In `backend/services/zone_service.py`, overrides are stored on `self.in_memory_override`. However, `backend/controllers/deps.py` instantiates `ZoneService(settings)` per request, causing all `PUT /api/config/zones` changes to vanish on subsequent calls.
4. **Path Traversal Security Vulnerabilities**: In `backend/controllers/video_controller.py:32` and `backend/services/video_service.py:53`, user-provided file names are concatenated directly into paths without `Path(name).name` sanitization, allowing directory traversal.
5. **Unused Spatial Fusion Module**: `resolve_riders_and_pedestrians` is imported in `backend/services/cv/engine.py:13` but never invoked in `process_frame()`, leaving mounted riders classified as pedestrians.
6. **Unbounded Memory Leaks**: In `tracker.py`, `direction.py`, and `crosswalk.py`, tracking IDs and historical direction vectors are stored in dictionaries that are never purged when tracks expire.
7. **Malformed Range Header Crash**: In `backend/services/video_service.py:65-66`, invalid `Range` headers raise unhandled `ValueError` resulting in HTTP 500 instead of HTTP 416.
8. **Unsafe Polygon Split Mean**: In `backend/services/safety/clustering.py:90-91`, empty half-polygons crash with `RuntimeError` during lane auto-clustering.

---

## 2. Frontend Subsystem Audit

### 2.1 Next.js 16 & Turbopack Setup
- **Version**: Next.js 16.4.3, React 19, Turbopack, Tailwind CSS v4.
- **Build Verification**: `pnpm --prefix frontend build` completes with exit code 0.
- **Type Safety Flag**: `next.config.mjs` sets `typescript: { ignoreBuildErrors: true }`. This must be removed once types are reconciled.
- **Styles Issue**: `globals.css` contains `@import 'shadcn/tailwind.css';`, which does not exist in `node_modules` (CLI tool, not CSS).

### 2.2 Brad Frost Atomic Design Compliance
- **Atoms**:
  - `components/ui/button.tsx`: **VIOLATION** — misplaced in `components/ui/` instead of `components/atoms/Button.tsx`, and completely unused dead code.
  - `components/atoms/Badge.tsx`: Inlines `<span className="status-dot" />` instead of composing `<StatusDot />`.
  - `components/atoms/StatusDot.tsx`: Compliant.
  - `components/atoms/Toast.tsx`: Compliant.
- **Molecules**:
  - `components/molecules/ExportButtonGroup.tsx`: Partially compliant (inlines raw button/anchor tags instead of Button atom).
  - `components/molecules/ProgressBanner.tsx`: Compliant.
  - `components/molecules/TelemetryBar.tsx`: Compliant.
  - `components/molecules/VideoScrubber.tsx`: Compliant.
- **Organisms**:
  - `components/organisms/AppHeader.tsx`: Inlines raw buttons/selects.
  - `components/organisms/EventsSidebar.tsx`: **VIOLATION** — Duplicates inline badge markup (`lines 91-94`) and inlines `<div className="green-dot" />` instead of using atomic `<Badge>` and `<StatusDot>`.
  - `components/organisms/EvidenceDrawer.tsx`: Compliant.
  - `components/organisms/VideoPlayerCanvas.tsx`: Compliant.
- **Templates**:
  - `components/templates/DashboardLayout.tsx`: Compliant.
- **Pages**:
  - `app/page.tsx`: **VIOLATION** — Line 414 inlines raw styled `<button className="reopen-drawer">` with an embedded icon directly in page code.

### 2.3 Detailed Frontend Bugs & Defects
1. **CRITICAL P0: Backend-Frontend DTO Schema Mismatch Causing UI Crash**:
   - Backend `views.event_views.TrafficEvent` returns: `tracking_id: int`, `start_time: float`, `end_time: float`, `duration_seconds: float`, `natural_language_explanation: str`, `evidence_frames: Optional[EvidenceFrames]`.
   - Frontend `lib/api.ts:TrafficEvent` expects: `track_ids: number[]`, `time_start: number`, `time_end: number`, `duration_sec: number`, `explanation?: string`, `evidence: EvidenceFrames`, `metrics: Record<string, any>`, `raw_json: Record<string, any>`.
   - **Fatal Crashes**:
     - `EventsSidebar.tsx:90`: `<span className="rule-code">TRK-{ev.track_ids.join(',')}</span>` -> `TypeError: Cannot read properties of undefined (reading 'join')`.
     - `EvidenceDrawer.tsx:31`: `selectedEvent.track_ids.join(', #')` -> `TypeError: Cannot read properties of undefined (reading 'join')`.
     - `EvidenceDrawer.tsx:47, 70, 93`: `selectedEvent?.evidence.entry_frame_url` -> `TypeError: Cannot read properties of undefined (reading 'entry_frame_url')` because `evidence` is undefined.
     - `EvidenceDrawer.tsx:129`: `selectedEvent?.metrics.angle_deg` -> `TypeError: Cannot read properties of undefined (reading 'angle_deg')`.
2. **Missing Zone Persistence (`saveZones` Never Invoked)**: `saveZones` is imported in `app/page.tsx:8` but never called anywhere. There is no "Save Layout" button in `VideoPlayerCanvas.tsx`, so user edits to calibration polygons are lost on reload.
3. **SVG Drag Coordinates Clamped Out-of-Bounds**: In `app/page.tsx:284-285`, coordinates are clamped to `[4200, 2200]` instead of the video/SVG resolution `[3840, 2160]`, allowing out-of-bounds coordinates to reach OpenCV.
4. **Missing Pointer Capture on Vertex Drag**: In `VideoPlayerCanvas.tsx`, `onPointerDown` does not call `setPointerCapture()`. Dragging quickly outside the SVG causes vertices to get stuck to the mouse cursor.
5. **Full Video Preset Cap Bug**: In `app/page.tsx:231`, selecting "Full Video" sets `maxFr = null`, which converts to `undefined` in payload. The backend defaults `req.max_frames or 300`, so "Full Video" runs only 300 frames (10s) instead of all frames.
6. **"AI Analyzed" Mode Hides Overlays**: If `annotatedVideoExists` is false and mode is "analyzed", overlays are hidden and raw video plays with no indication.
7. **Unhandled Clipboard API Rejection**: In `app/page.tsx:406-411`, `navigator.clipboard.writeText` is unhandled and can throw an unhandled Promise rejection.
8. **`<video>` Error & State Desynchronization**: No `onError` handler; switching videos leaves `isPlaying` out of sync.

---

## 3. Notebook & Evaluation Pipeline Audit

### 3.1 Notebook Health & Static Code Audit
- **File**: `backend/notebooks/cctv_safety_pipeline.ipynb` (69 cells: 35 Markdown, 34 Code).
- **Broken Imports (Cells 58 & 64)**: `import pandas as pd` and `df_cases = pd.DataFrame(edge_cases)` fail with `ModuleNotFoundError: No module named 'pandas'` because `pandas` is not in `REQUIRED_PACKAGES` (Cell 2) and not in `.venv`.
- **Unexecuted Cells**: Cell 58 (benchmark metrics table and speed profiling) and Cell 64 (edge cases and velocity decision boundary plot) were never executed (`execution_count: null`, empty outputs).
- **Duplicate Section Headers**: Cell 63 and Cell 65 are both titled `## 11.`.

### 3.2 Cell Output vs. Disk Artifact Inconsistencies
- Cell 56 printed output reports **52 detected events** over the full 688 frames ($22.9\text{s}$).
- In contrast, `data/output/detected_events.json` contains only **22 events** from an earlier 100-frame preview run ($3.3\text{s}$).
- Cell 66 reports finding **125 evidence cards** in `data/output/evidence_cards/`, accumulated across repeated runs without folder purging.

### 3.3 Benchmark Evaluation Against `data/eval_gt.json`
- `data/eval_gt.json` defines 20 ground-truth events across 4 categories:
  - `WRONG_WAY`: 6 events (GT-01..04, GT-15, GT-18)
  - `CROSSWALK_RIDING`: 6 events (GT-05..08, GT-16, GT-19)
  - `EXEMPT_WALKING`: 4 events (GT-09..11, GT-17)
  - `INSUFFICIENT_EVIDENCE`: 4 events (GT-12..14, GT-20)
- **Temporal Horizon Disconnect**:
  - The ground-truth events span from $t = 2.0\text{s}$ to $t = 109.2\text{s}$.
  - The video clip `intersection_01.mp4` has only 688 frames at 30 FPS = **$22.93\text{ seconds}$**.
  - Events GT-05 through GT-20 ($t = 29.0\text{s}$ to $109.2\text{s}$) physically do not exist in the $22.9\text{s}$ video clip!
  - When duration filtering is applied (`video_duration_s = 22.93`), only 4 events remain (all `WRONG_WAY`), dropping GT for all other 3 categories to 0.

### 3.4 Accuracy Metrics Breakdown
#### Filtered Evaluation (Matching Duration $22.93\text{s}$):
| Category | GT Count | Detected ($Pred$) | True Pos ($TP$) | False Pos ($FP$) | False Neg ($FN$) | Precision | Recall | F1-Score |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `WRONG_WAY` | 4 | 35 | 4 | 31 | 0 | 0.114 | 1.000 | **0.205** |
| `CROSSWALK_RIDING` | 0 | 2 | 0 | 2 | 0 | 0.000 | 0.000 | **0.000** |
| `EXEMPT_WALKING` | 0 | 15 | 0 | 15 | 0 | 0.000 | 0.000 | **0.000** |
| `INSUFFICIENT_EVIDENCE` | 0 | 0 | 0 | 0 | 0 | 0.000 | 0.000 | **0.000** |
| **Overall System** | **4** | **52** | **4** | **48** | **0** | **0.077** | **1.000** | **0.143** |

*Verified Matches*:
- GT-01 ($2.0\text{--}5.5\text{s}$) matches EV-03 ($1.5\text{--}3.87\text{s}$, $IoU = 0.468$)
- GT-02 ($8.0\text{--}11.2\text{s}$) matches EV-14 ($7.03\text{--}11.53\text{s}$, $IoU = 0.711$)
- GT-03 ($14.2\text{--}17.8\text{s}$) matches EV-29 ($12.97\text{--}15.0\text{s}$, overlap $> 0.3\text{s}$)
- GT-04 ($22.0\text{--}25.4\text{s}$) matches EV-50 ($20.63\text{--}22.9\text{s}$, overlap $> 0.3\text{s}$)

#### Unfiltered Evaluation (Against All 20 GT Events):
| Category | GT Count | Detected ($Pred$) | True Pos ($TP$) | False Pos ($FP$) | False Neg ($FN$) | Precision | Recall | F1-Score |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `WRONG_WAY` | 6 | 35 | 4 | 31 | 2 | 0.114 | 0.667 | **0.195** |
| `CROSSWALK_RIDING` | 6 | 2 | 0 | 2 | 6 | 0.000 | 0.000 | **0.000** |
| `EXEMPT_WALKING` | 4 | 15 | 0 | 15 | 4 | 0.000 | 0.000 | **0.000** |
| `INSUFFICIENT_EVIDENCE` | 4 | 0 | 0 | 0 | 4 | 0.000 | 0.000 | **0.000** |
| **Overall System** | **20** | **52** | **4** | **48** | **16** | **0.077** | **0.200** | **0.111** |

### 3.5 Analysis of Challenging & Failed Cases
1. **31 False Positive `WRONG_WAY` Events**:
   - `LaneAutoDetector` has loose `bidir_threshold = 0.40`. During the 40-frame warmup, dominant southbound flow causes the 2-way road to be permanently classified as a single one-way southbound lane.
   - All legal northbound vehicles travelling along the road produce negative cosine alignment and are flagged as `WRONG_WAY`.
2. **15 False Positive `EXEMPT_WALKING` Events & 2 False Positive `CROSSWALK_RIDING` Events**:
   - `detect_crosswalk()` flags any motorcycle entering the crosswalk polygon without checking whether the movement is along normal roadway flow (`is_normal_lane_transit`).
   - Ordinary traffic driving down the street crossing `crosswalk_top` at low speed is flagged as `EXEMPT_WALKING`, and at normal speed as `CROSSWALK_RIDING`.
3. **16 False Negatives (GT-05 to GT-20)**:
   - Events occur between $t = 29.0\text{s}$ and $t = 109.2\text{s}$, which fall completely outside the 688-frame ($22.93\text{s}$) video file.
4. **Schema Mismatch on `INSUFFICIENT_EVIDENCE`**:
   - Borderline counter-flow tracks are assigned `event_type = "WRONG_WAY"` with `verdict = "INSUFFICIENT_EVIDENCE"`, preventing category matching with `INSUFFICIENT_EVIDENCE` GT events.
5. **Tracking Fragmentation & Duplicate Alerts**:
   - 72 motorcycle tracks were created for ~10-15 actual vehicles due to three-wheeler occlusions. Each track triggers its own alert.

### 3.6 Execution Speed Benchmarks: Claimed vs. Actual
- **Claimed**: $36.2\text{ ms/frame}$ CPU latency ($27.6\text{--}28.5\text{ FPS}$).
- **Empirical Measured Profiling (CPU PyTorch / Intel/AMD Windows)**:
  - YOLO11m Inference (`imgsz=960`): **$218.6\text{ ms/frame}$**
  - Overlay Alpha Blending (`cv2.addWeighted` on 4K array): **$11.2\text{ ms/frame}$**
  - Multi-Object Tracking & HUD Drawing: **$25.4\text{ ms/frame}$**
  - 4K Video Encoding (`cv2.VideoWriter`, `mp4v` codec): **$65.0\text{ ms/frame}$**
  - Evidence Keyframes Extraction & 3-Panel Card Generation: **$190.7\text{ ms/event}$**
  - **Total Pipeline Execution Time**: **$350.9\text{ seconds}$** for 688 frames = **$\sim 1.96\text{--}2.0\text{ FPS}$** ($\sim 510\text{ ms/frame}$).
  - *Conclusion*: Real-time $28.5\text{ FPS}$ is only attainable with GPU acceleration (CUDA / TensorRT). On CPU, true throughput is $\sim 2.0\text{ FPS}$.

---

## 4. Operational Assumptions and System Constraints

1. **Hardware & Acceleration**:
   - CPU execution yields $\sim 2\text{ FPS}$ for 4K video processing; GPU acceleration (CUDA) is required for real-time inference ($> 25\text{ FPS}$).
2. **Camera Perspective**:
   - Monocular high-angle CCTV mounted at an intersection with perspective foreshortening. Bounding-box height $H$ is used to normalize velocity across scale.
3. **Monorepo File Constraints**:
   - All backend Python files must remain strictly <= 100 LOC.
   - Flat MVC + Services layout must be strictly preserved (`controllers`, `models`, `views`, `services/safety`, `services/cv`, `config.py`, `main.py`).
4. **Frontend Architecture Constraints**:
   - Next.js 16 with Brad Frost Atomic Design (`components/atoms`, `components/molecules`, `components/organisms`, `components/templates`, `app/page.tsx`).
5. **Git Constraint**:
   - Strict prohibition: no git commits may be made without explicit user authorization.

---

## 5. Comprehensive Remediation Roadmap

The monorepo remediation is partitioned into four focused milestones following this audit report:

### Milestone 3: Backend Remediation
- **LOC Reductions (<= 100 LOC)**:
  - Refactor `backend/services/cv/annotator.py` (111 -> <= 100 LOC).
  - Refactor `backend/services/cv/tracker.py` (107 -> <= 100 LOC).
  - Refactor `backend/services/safety/crosswalk.py` (103 -> <= 100 LOC).
- **Bug Fixes**:
  - Fix fatal `AttributeError` in `engine.py` / `pedestrian.py` by providing `sv.PolygonZone` instances with `.trigger()`.
  - Fix `PipelineService._run_job` to write annotated video output via `cv2.VideoWriter` and serialize `detected_events.json`.
  - Fix `ZoneService` singleton persistence in `deps.py`.
  - Sanitize file paths in `video_controller.py` and `video_service.py`.
  - Activate `resolve_riders_and_pedestrians` in `engine.py`.
  - Evict stale tracks to eliminate memory leaks.
- **Verification**: Run `pytest backend/tests/` (all 12 passing) and verify LOC for all 43 files.

### Milestone 4: Frontend Remediation
- **DTO Reconciliation**:
  - Update `lib/api.ts` to normalize backend `TrafficEvent` (support both `tracking_id`/`track_ids`, `start_time`/`time_start`, `evidence_frames`/`evidence`, safe metrics).
  - Implement defensive rendering in `EventsSidebar.tsx` and `EvidenceDrawer.tsx`.
- **Atomic Design Conformance**:
  - Replace/remove `components/ui/button.tsx` with compliant `components/atoms/Button.tsx`.
  - Compose `<StatusDot>` in `Badge.tsx` and `EventsSidebar.tsx`.
  - Move inline reopen button in `app/page.tsx:414` to an atomic/molecular component.
- **Feature & Bug Fixes**:
  - Implement "Save Layout" button in `VideoPlayerCanvas.tsx` wired to `saveZones()`.
  - Correct SVG drag clamping from 4200/2200 to 3840/2160.
  - Add pointer capture on canvas drag.
  - Fix "Full Video" preset to pass full video frame count.
  - Remove `typescript.ignoreBuildErrors: true` from `next.config.mjs` and clean up `globals.css`.
- **Verification**: Run `pnpm --prefix frontend build` without errors or bypassed type checking.

### Milestone 5: Notebook & Pipeline Remediation
- **Dependency & Import Fixes**:
  - Add `pandas` to `REQUIRED_PACKAGES` in Cell 2.
  - Ensure Cell 58 and Cell 64 execute cleanly without errors.
- **Cell Output Consistency**:
  - Run cells end-to-end to generate consistent outputs and graphs.
  - Fix section numbering (Cell 65 -> Section 12, Cell 67 -> Section 13).
  - Align `detected_events.json` on disk with notebook outputs.
- **Algorithmic Hardening**:
  - Add normal lane flow suppression to `detect_crosswalk()`.
  - Increase `bidir_threshold` to 0.75 and apply KMeans lane clustering to prevent one-way road collapse.
  - Tighten wrong-way threshold to -0.60 with lateral velocity dominance.
  - Document the 22.9s video duration vs. 109s benchmark scope clearly in markdown cells.
- **Verification**: Execute notebook and verify precision/recall/F1 metrics and execution speed table.

### Milestone 6: Final Verification & Integrity Audit
- 12/12 backend tests passing.
- Frontend build succeeds with zero type bypass.
- Notebook runs cleanly end-to-end with verified cell outputs.
- Independent Forensic Audit verification (CLEAN verdict).
- Git status verified (zero commits made).
