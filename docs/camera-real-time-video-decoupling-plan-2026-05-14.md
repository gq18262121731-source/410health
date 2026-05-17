# Camera Real-Time Video Decoupling Plan (2026-05-14)

## Goal

Stabilize the elder-care camera demo into a low-latency, explainable, and shippable pipeline.

This plan explicitly separates:

1. Video acquisition
2. AI analysis
3. Frontend business UI

The immediate product goal is not "perfect architecture". The goal is:

- restore a usable low-latency live picture
- stop old-frame accumulation
- stop Flutter Web from acting as a frame-by-frame decoder
- keep AI analysis available without blocking video

---

## 1. Current Diagnosis

## 1.1 What is already working

The backend RTSP acquisition path is basically proven:

- RTSP source: `tcp/av0_1`
- backend acquisition: OpenCV
- backend steady pull: around `8~10 fps`
- backend MJPEG output: verified working
- hub mapping: stabilized to a single active hub instance

This means the current main bottleneck is no longer:

- camera connectivity
- raw RTSP reachability
- OpenCV continuous pull capability

## 1.2 What is failing now

The unstable part is the end-to-end display chain.

Observed failure modes:

- old frames are displayed instead of latest frames
- display delay grows to tens of seconds
- Flutter Web main thread becomes overloaded
- snapshot requests may reset or fail
- unrelated business polling and 401 handling further increase rebuild pressure

This is consistent with two classes of accumulation:

1. Frame accumulation
   - historical frames are processed/displayed instead of dropped
2. UI/request accumulation
   - frontend request retries, decode work, and rebuild work pile up

## 1.3 Core engineering rule

Real-time systems must prefer freshness over completeness.

The system must follow:

```text
Always chase the newest frame.
Drop old frames.
Skip analysis if busy.
Never queue historical frames for "honest" processing.
```

---

## 2. Target Architecture

The system should be split into three independent chains:

```text
RTSP Camera
  -> CameraFrameHub (OpenCV pull)
  -> latest_frame (memory only)

latest_frame
  -> Native Video Preview API/Page
  -> AI Analysis Scheduler/Worker
  -> stream-status metrics

Flutter UI
  -> embed native preview page
  -> render controls / alarms / AI result state
  -> never decode video frames itself on Web
```

High-level rule:

- video path must not block on AI
- AI path must not block on video
- business UI must not participate in frame transport/decoding on Web

---

## 3. Backend Plan

## 3.1 Acquisition Chain

Keep the existing proven RTSP acquisition design:

- fixed RTSP path: `tcp/av0_1`
- OpenCV is the primary implementation
- no aggressive ffmpeg/snapshot fallback on transient read failure
- reconnect only after consecutive failures
- hub maintains only one latest frame in memory

### Required hub behavior

Every successful frame pull must:

1. overwrite `_latest_frame`
2. update `_latest_frame_at`
3. update `_latest_frame_size`
4. update capture metrics

The hub must not become a historical frame queue.

Forbidden behavior:

- unbounded `queue.put(frame)` for analysis or preview consumers
- replaying stale frames to stay "complete"

### Required acquisition metrics

Keep and expose:

- `capture_fps`
- `processed_fps`
- `active_url`
- `failed_count`
- `last_error`
- `last_read_elapsed_ms`
- `latest_frame_at`
- `latest_frame_size`
- `hub_object_id`
- `hub_cache_key`

Add:

- `latest_frame_age_ms`

Definition:

```text
latest_frame_age_ms = now - latest_frame_at
```

Target:

- normal state: `< 300~500ms`

This is one of the most important end-to-end freshness indicators.

---

## 3.2 Snapshot / Latest-Frame API

Keep one lightweight latest-frame HTTP endpoint:

- existing: `/api/v1/camera-sources/active/snapshot`
- optional alias later: `/api/v1/camera-sources/active/latest-frame.jpg`

The semantics must be strict:

1. return current `latest_frame` bytes from hub memory
2. never reopen camera
3. never perform fresh RTSP capture
4. never read from disk
5. never run any model
6. never do expensive on-demand work

### Cache policy

Response must include:

```text
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
Pragma: no-cache
Expires: 0
```

### Failure behavior

If no valid latest frame is present:

- return `503`
- return quickly

Do not mask missing frames by launching fallback capture logic inside this endpoint.

---

## 3.3 Native Video Preview Page

Primary Web display path should be:

- `/api/v1/camera-sources/active/video-preview`

This page must be a pure HTML/JS preview layer, independent from Flutter frame decoding.

### Required behavior

1. use latest-frame polling, not Flutter-driven per-frame updates
2. request next frame only if previous one completed
3. update only the displayed image element
4. keep rendering logic native to browser

### First stable profile

- polling interval: `200ms`
- target displayed rate: about `5 fps`
- priority: low latency and stability, not high frame count

### Required anti-accumulation rule

Pseudo-rule:

```js
if (loading) return;
loading = true;
request next frame
onload/onerror -> loading = false
```

This must remain true even after later tuning.

### Page-local metrics

The page should display at least:

- preview fps
- optional frame age / state later

So the preview layer can be debugged independently from Flutter.

---

## 3.4 AI Analysis Chain

AI analysis must be an asynchronous sampling pipeline, not a per-frame obligation.

### Required structure

1. acquisition loop continuously refreshes `latest_frame`
2. analysis scheduler triggers periodically
3. scheduler asks for current `latest_frame`
4. if worker busy, skip this cycle
5. no historical frame queue

### Initial recommended cadence

- pose/fall analysis every `500ms ~ 1000ms`

### Forbidden design

Do not do:

```text
read frame -> analyze -> display -> read next frame
```

Do not do:

```text
enqueue every frame for later analysis
```

### Required analysis metrics

Add and expose:

- `analysis_enabled`
- `analysis_busy`
- `analysis_last_started_at`
- `analysis_last_finished_at`
- `analysis_last_elapsed_ms`
- `analysis_skipped_count`
- `analysis_last_error`

These metrics allow us to prove:

- analysis speed
- whether analysis blocks the live path
- whether skip-on-busy works

---

## 3.5 Business Polling Suppression

Video debugging and demo playback should not be slowed by unrelated failing requests.

Observed problem classes:

- repeated `401`
- unrelated profile/status polling
- provider error handling causing rebuild churn

### Required behavior for video page

When the family camera page is active:

- pause unrelated polling where possible
- avoid repeated retry storms for unrelated endpoints
- isolate video page from non-video provider churn

Minimum keepers:

- camera stream status
- AI status
- alarms (if strictly required for demo)

Everything else should be either paused or rate-limited during video-focused operation.

---

## 4. Frontend Plan

## 4.1 Flutter Web Role

Flutter Web should no longer be responsible for:

- frame-by-frame image decode
- MJPEG long-stream decode behavior
- direct latest-frame polling/render loop

Flutter Web should only:

- embed native preview page
- render controls
- render alarm state
- render AI state/results

### Web video embedding

Use:

- `HtmlElementView`
- iframe to `/api/v1/camera-sources/active/video-preview`

This keeps browser-native video/image handling outside Flutter's per-frame rendering path.

---

## 4.2 UI Rebuild Isolation

Even after removing Flutter from frame decoding, page rebuild pressure still matters.

### Required rule

Do not `watch<CameraProvider>()` for the whole page if only a small section needs a subset of data.

Use:

- `context.select(...)`
- narrow provider reads
- isolated widgets for:
  - video shell
  - diagnostics
  - controls
  - alarms
  - AI status

### Outcome

- alarm changes should not rebuild video shell
- diagnostics refresh should not rebuild unrelated controls
- AI result updates should not trigger broad page refresh

---

## 4.3 Video Page Scope

The Web camera page should have two clear layers:

1. native preview frame
2. Flutter business frame

Flutter should not try to own timing of image refresh anymore.

---

## 5. Rollout Order

## Phase 1: Stop-loss and restore usable low-latency picture

1. keep OpenCV RTSP acquisition path unchanged
2. ensure `/active/snapshot` only returns hub memory latest frame
3. serve `/active/video-preview` as pure HTML latest-frame page
4. make Flutter embed that preview page
5. disable Flutter-driven latest-frame / `Image.memory` Web path
6. reduce unrelated polling on video page

### Acceptance

- picture appears within `1~3 seconds`
- delay visibly drops below `1 second`
- no replay of tens-of-seconds-old frames
- page no longer collapses under frame decode churn

---

## Phase 2: Complete observability

Backend must expose:

- `latest_frame_age_ms`
- snapshot response timing
- analysis elapsed time
- analysis skipped count

Frontend should show:

- `capture_fps`
- `latest_frame_age_ms`
- `analysis_busy`
- `analysis_last_elapsed_ms`

### Acceptance

- delay source can be attributed to a specific layer
- no more "guessing by feel"

---

## Phase 3: Re-enable AI overlay/results cleanly

1. keep video stable first
2. run analysis asynchronously on sampled latest frames
3. deliver result state via websocket or low-rate polling
4. let Flutter show result state, not own frame transport

### Acceptance

- live video remains smooth enough
- AI results continue updating
- slow analysis lowers result refresh rate only, not video latency

---

## Phase 4: Mobile validation

If final product target is Flutter mobile, Web should not be treated as the ultimate playback benchmark.

Use Web for:

- demo staging
- transport debugging
- fast local verification

Use mobile for:

- final user experience validation
- final acceptable video path decisions

---

## 6. Acceptance Criteria

## Backend acquisition

- `capture_fps >= 8`
- `processed_fps >= 8`
- `failed_count = 0`
- `last_error = null`
- `latest_frame_age_ms < 300~500ms`

## Native preview page

- first picture within `1~3 seconds`
- end-to-end visible delay `< 1 second`
- no obvious replay of historical frames
- no request pile-up

## Flutter page

- no build-phase state errors
- no Flutter-driven per-frame decode path on Web
- UI remains responsive

## AI chain

- busy => skip
- no historical queue growth
- results update without blocking video

---

## 7. Risk Register

## Risk A: Snapshot endpoint accidentally reintroduces heavy work

Symptoms:

- `ERR_CONNECTION_RESET`
- long response times
- preview blackouts

Mitigation:

- enforce "memory frame only" semantics
- reject or fast-fail when no frame available

## Risk B: Native preview page still accumulates requests

Symptoms:

- browser network backlog
- preview still delays despite latest-frame design

Mitigation:

- hard `loading` gate
- do not launch second request before first completes

## Risk C: Flutter page still rebuilds too broadly

Symptoms:

- requestAnimationFrame handler spikes
- responsive video but sluggish page shell

Mitigation:

- replace broad `watch` usage with `select`
- split page into smaller listening widgets

## Risk D: Analysis still blocks acquisition indirectly

Symptoms:

- capture fps drops when models enabled
- frame age grows when analysis starts

Mitigation:

- analysis scheduler must skip when busy
- analysis must sample latest frame only

---

## 8. Rollback Strategy

If the latest-frame HTML preview path still underperforms:

1. keep backend OpenCV acquisition unchanged
2. keep AI analysis decoupling work
3. test MJPEG inside the native preview page again
4. compare:
   - native HTML MJPEG
   - native HTML latest-frame polling

Fallback principle:

- compare preview strategies only inside native HTML
- never revert to Flutter Web per-frame decode path as the primary demo route

---

## 9. Immediate Next Tasks

1. finalize backend metrics:
   - `latest_frame_age_ms`
   - snapshot response timing
   - analysis elapsed
   - analysis skipped count
2. reduce unrelated video-page business polling / fix repeated 401 churn
3. validate native preview page latency with manual motion test
4. only after that, reattach AI result display at low frequency

---

## 10. One-Sentence System Rule

```text
Video always follows latest_frame through a native browser preview layer, AI always samples asynchronously and skips when busy, and Flutter only owns business UI rather than frame-by-frame Web video decoding.
```

---

## 11. Current Code Conflicts That Must Be Resolved

This section documents logical conflicts between the target design and the current codebase state.

These are not optional cleanups. They must be resolved to avoid mixed-mode behavior.

### 11.1 Web video path must not coexist with Flutter-driven frame transport

Current target design:

```text
Web video = iframe/native HTML preview only
```

Therefore the following Web-side behaviors must not remain active at the same time:

- provider-driven latest-frame polling
- provider-driven MJPEG decoding logic
- Flutter `Image.memory` as the primary Web live video renderer

Required rule:

```text
On Web, only one live video transport path may exist.
```

If iframe/native preview is chosen, then Web must not also:

- start a snapshot polling timer in `CameraProvider`
- start a websocket frame stream for preview
- treat `frameBytes` as the live Web preview source

### 11.2 `CameraProvider.startFrameRefresh()` must respect the chosen Web strategy

If Web uses native iframe preview:

- `startFrameRefresh()` may still enable diagnostics refresh
- but it must not start:
  - `_startWebSnapshotLoop()`
  - `_startFrameStream()`

Otherwise Web will run two transport loops:

1. iframe preview traffic
2. provider preview traffic

This recreates pressure and invalidates latency measurements.

### 11.3 `saveSetupConfig()` restart behavior must not secretly reactivate old preview transport

If `autoRefresh == true`, save/reload flows often restart streams.

Required rule:

```text
On Web + remote camera mode, save/reload must not automatically restart Flutter frame transport.
```

Otherwise a settings save can silently re-enable:

- websocket preview
- snapshot polling

while the iframe preview is already running.

### 11.4 `frameBytes`, `hasFrame`, and `streamLabel` semantics diverge on Web iframe mode

When Web preview is iframe-based:

- `frameBytes` may remain null forever
- `hasFrame` must not be used as the source of truth for "is remote video working"
- `streamLabel` must not imply that Flutter itself is rendering live frames

Required rule:

- iframe preview status should come from native preview page health or backend status
- Flutter `frameBytes` should be treated as non-authoritative for Web preview mode

### 11.5 Flutter-side receive/client FPS are no longer authoritative on Web iframe mode

If the browser-native page owns video display:

- Flutter-side `receiveFps`
- Flutter-side `clientFps`

do not directly measure the live preview anymore.

In Web iframe mode, the authoritative display-side metrics should come from:

- native preview page JS
- backend stream-status metrics

Flutter can still display those metrics, but should not pretend to calculate them locally from decoded frames it no longer owns.

### 11.6 Business polling suppression must be route-aware, not global by accident

The plan requires reducing unrelated request churn on the video page.

This does **not** mean blindly disabling care/alarm/profile refresh app-wide.

Required rule:

- only suppress or rate-limit non-video polling while the video-focused route is active
- do not break unrelated screens by globally disabling providers

### 11.7 AI analysis must not assume local preview ownership

Current code still contains local-preview analysis hooks.

Required rule:

- browser-local preview analysis logic may remain for local camera experiments
- but remote RTSP mode must not depend on browser-side frame capture for AI

For remote mode:

- AI analysis must consume backend `latest_frame`
- not browser-extracted frames

---

## 12. File-by-File Change Map

This is the authoritative mapping from architecture to concrete files.

## 12.1 Backend acquisition and preview

### `backend/services/camera_stream_hub.py`

Responsibilities:

- continuous RTSP/OpenCV acquisition
- maintain `latest_frame`
- maintain acquisition metrics
- never become a historical frame queue

Required changes:

- ensure `latest_frame_age_ms` is computed in status
- expose analysis-safe access patterns if needed
- preserve skip-old-frame semantics

### `backend/api/camera_source_api.py`

Responsibilities:

- `/active/snapshot`
- `/active/stream-status`
- `/active/video-preview`

Required changes:

- `/active/snapshot` must remain memory-only latest-frame
- `/active/video-preview` must remain pure HTML/JS preview
- preview page must gate concurrent requests with `loading`
- preview page polling interval must default to `200ms`

## 12.2 Backend analysis path

### `backend/services/frame_analysis_worker_service.py`

Responsibilities:

- analysis worker lifecycle
- skip-on-busy behavior
- timing metrics

Required changes:

- add explicit elapsed/skip metrics
- ensure no historical frame queue accumulates

### `backend/dependencies.py`

Responsibilities:

- hub/service wiring
- worker startup/shutdown wiring

Required changes:

- expose clean access to active hub and active analysis services
- avoid hidden duplicate hub/service paths

## 12.3 Flutter Web video shell

### `mobile/flutter_app/lib/features/camera/screens/family_camera_screen.dart`

Responsibilities:

- page composition
- choose local preview vs remote preview
- embed native iframe preview on Web

Required changes:

- remote Web mode must use iframe/native preview only
- do not use `frameBytes` as Web live preview truth
- isolate diagnostics from broad page rebuilds

### `mobile/flutter_app/lib/features/camera/widgets/remote_video_iframe_web.dart`

Responsibilities:

- host iframe/native preview page

Required changes:

- stable iframe embedding only
- no attempt to decode video frames in Flutter

## 12.4 Flutter camera provider

### `mobile/flutter_app/lib/features/camera/providers/camera_provider.dart`

Responsibilities:

- camera diagnostics state
- remote control state
- optional non-Web preview transport

Required changes:

- Web iframe mode must not start snapshot polling
- Web iframe mode must not start websocket preview transport
- `saveSetupConfig()` must not re-enable old Web preview transport
- old `_startWebSnapshotLoop()` path should be deleted once fully retired

## 12.5 Business polling sources

### `mobile/flutter_app/lib/features/care/providers/care_provider.dart`

Responsibilities:

- care access profile refresh

Required changes:

- allow video route to suppress or rate-limit automatic refresh
- prevent repeated 401/retry churn while video debugging

### `mobile/flutter_app/lib/main.dart`

Responsibilities:

- global provider wiring
- auth/session/alarm startup

Required changes:

- ensure route-scoped suppression logic can be applied without breaking app boot

---

## 13. Step-by-Step Execution Checklist

This is the implementation order that avoids logical backtracking.

## Step 1: Normalize the backend latest-frame contract

Files:

- `backend/services/camera_stream_hub.py`
- `backend/api/camera_source_api.py`

Actions:

1. confirm `/active/snapshot` only reads hub memory
2. confirm no on-demand RTSP capture happens in this endpoint
3. add `latest_frame_age_ms`
4. add snapshot response timing logs if missing

Pass criteria:

- `stream-status` shows non-null `latest_frame_at`
- `latest_frame_age_ms < 300~500ms`
- repeated `/active/snapshot` calls do not trigger new capture logic

Rollback:

- keep acquisition path unchanged
- revert only snapshot endpoint logic if it accidentally reintroduced heavy work

## Step 2: Freeze the native preview page behavior

Files:

- `backend/api/camera_source_api.py`

Actions:

1. `/active/video-preview` must use pure HTML/JS polling
2. polling interval fixed at `200ms`
3. single in-flight request rule enforced
4. page-local fps indicator visible

Pass criteria:

- direct open of `/active/video-preview` shows image within `1~3s`
- no obvious replay of historical frames
- browser network panel shows at most one in-flight snapshot request from the page

Rollback:

- if latest-frame page still fails, test native HTML MJPEG inside the same page
- do not revert to Flutter frame decoding as the primary fallback

## Step 3: Disable conflicting Web preview transport in Flutter

Files:

- `mobile/flutter_app/lib/features/camera/providers/camera_provider.dart`
- `mobile/flutter_app/lib/features/camera/screens/family_camera_screen.dart`

Actions:

1. Web remote mode must not start websocket preview
2. Web remote mode must not start snapshot polling in provider
3. Web remote mode must embed iframe preview only
4. `saveSetupConfig()` must not restart old preview transport on Web

Pass criteria:

- Web camera page creates one visible preview path only
- no duplicate preview requests originate from Flutter provider
- Flutter console no longer shows repeated frame transport work for Web preview

Rollback:

- if iframe embedding fails, validate `/active/video-preview` directly outside Flutter first

## Step 4: Reduce business churn on the video route

Files:

- `mobile/flutter_app/lib/features/care/providers/care_provider.dart`
- possibly route entry files that trigger provider refresh

Actions:

1. identify auto-refresh sources for care/profile requests
2. suppress or rate-limit them while camera page is active
3. ensure repeated 401 does not cause retry/rebuild storms

Pass criteria:

- no repeated `access-profile/me` 401 churn while video page is active
- requestAnimationFrame violations reduce materially

Rollback:

- if route-aware suppression is too invasive, temporarily disable only the offending refresh timer in debug/demo builds

## Step 5: Restore AI as a separate sampled chain

Files:

- `backend/services/frame_analysis_worker_service.py`
- related camera analysis service wiring

Actions:

1. schedule analysis at `500ms~1000ms`
2. if busy, skip
3. no historical frame queue
4. expose elapsed/skip/error metrics

Pass criteria:

- video latency does not worsen when analysis enabled
- analysis metrics show skips instead of growing queue behavior

Rollback:

- if analysis still harms preview, disable analysis and validate pure video path first

---

## 14. Verification Commands and Observation Points

## 14.1 Backend health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

Expected:

- `status = ok`

## 14.2 Backend stream status

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/camera-sources/active/stream-status | ConvertTo-Json -Depth 6
```

Watch:

- `capture_fps`
- `processed_fps`
- `latest_frame_at`
- `latest_frame_size`
- `latest_frame_age_ms`
- `failed_count`
- `last_error`
- `active_url`

## 14.3 Native preview page

Open:

- `http://127.0.0.1:8000/api/v1/camera-sources/active/video-preview`

Watch:

- first image time
- hand-wave latency
- whether displayed motion is current or historical
- browser network concurrency for snapshot requests

## 14.4 Flutter page

Open:

- `http://127.0.0.1:5182/`

Watch:

- whether preview appears at all
- whether iframe preview mirrors native preview latency
- whether unrelated business errors still spam console
- whether requestAnimationFrame violations materially decrease

---

## 15. Logic Review Summary

After re-evaluating the plan against the current codebase, the most important logical corrections are:

1. Web preview must have exactly one live transport path.
2. Flutter-side `frameBytes` cannot remain the source of truth for Web iframe mode.
3. `/active/snapshot` must stay memory-only, or the whole latest-frame strategy collapses.
4. Business polling suppression must be route-scoped, not app-wide by accident.
5. AI analysis must consume backend latest frames, not browser-captured frames, in remote RTSP mode.

These points are mandatory. If any of them are violated, the system will drift back into mixed-mode behavior and stale-frame accumulation.
