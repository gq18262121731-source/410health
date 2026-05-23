const ENABLE_COLOR_SKELETON = true;
const ENABLE_PART_BOXES = true;
const ENABLE_TARGET_AURA = true;
const ENABLE_TARGET_PULSE = true;
const ENABLE_TARGET_BBOX = true;
const POSE_CONFIDENCE_THRESHOLD = 0.2;

const overlayStats = window.__VISION_OVERLAY_STATS__ || {
  draws: [],
  reset() {
    this.draws = [];
  },
  record(sample) {
    this.draws.push(sample);
    if (this.draws.length > 600) {
      this.draws.splice(0, this.draws.length - 600);
    }
  },
  snapshot() {
    const values = (key) => this.draws
      .map((item) => item[key])
      .filter((value) => Number.isFinite(value));
    return {
      count: this.draws.length,
      avgTotalMs: statAverage(values("totalMs")),
      maxTotalMs: statMax(values("totalMs")),
      avgSkeletonMs: statAverage(values("skeletonMs")),
      maxSkeletonMs: statMax(values("skeletonMs")),
      avgBodyBoxMs: statAverage(values("bodyBoxMs")),
      maxBodyBoxMs: statMax(values("bodyBoxMs")),
      avgHighlightMs: statAverage(values("highlightMs")),
      maxHighlightMs: statMax(values("highlightMs")),
      avgObjects: statAverage(values("objects")),
      last: this.draws.at(-1) || null,
    };
  },
};
window.__VISION_OVERLAY_STATS__ = overlayStats;

const OVERLAY_FALL_STATE_LABELS = {
  normal: "Normal",
  unstable: "Unstable",
  falling: "Fall Risk",
  fallen_candidate: "Down Risk",
  fallen_confirmed: "Fall Confirmed",
  cooldown: "Recovering",
};

const OVERLAY_BEHAVIOR_LABELS = {
  standing: "Standing",
  walking: "Walking",
  sitting: "Sitting",
  bending: "Bending",
  lying: "Lying",
  unknown: "Unknown",
};

const BODY_PART_COLORS = {
  head: "#45D8FF",
  torso: "#FF5E5B",
  leftArm: "#4F83FF",
  rightArm: "#39D98A",
  leftLeg: "#FFD166",
  rightLeg: "#B57CFF",
  keypoint: "#F7FAFC",
  keypointStroke: "#081017",
};

const SKELETON_SEGMENTS = [
  {
    accentColor: BODY_PART_COLORS.head,
    edges: [
      ["nose", "left_eye"],
      ["nose", "right_eye"],
      ["left_eye", "right_eye"],
      ["left_eye", "left_ear"],
      ["right_eye", "right_ear"],
    ],
  },
  {
    accentColor: BODY_PART_COLORS.torso,
    edges: [
      ["left_shoulder", "right_shoulder"],
      ["left_shoulder", "left_hip"],
      ["right_shoulder", "right_hip"],
      ["left_hip", "right_hip"],
    ],
  },
  {
    accentColor: BODY_PART_COLORS.leftArm,
    edges: [
      ["left_shoulder", "left_elbow"],
      ["left_elbow", "left_wrist"],
    ],
  },
  {
    accentColor: BODY_PART_COLORS.rightArm,
    edges: [
      ["right_shoulder", "right_elbow"],
      ["right_elbow", "right_wrist"],
    ],
  },
  {
    accentColor: BODY_PART_COLORS.leftLeg,
    edges: [
      ["left_hip", "left_knee"],
      ["left_knee", "left_ankle"],
    ],
  },
  {
    accentColor: BODY_PART_COLORS.rightLeg,
    edges: [
      ["right_hip", "right_knee"],
      ["right_knee", "right_ankle"],
    ],
  },
];

const SKELETON_EDGES = SKELETON_SEGMENTS.flatMap((segment, segmentIndex) => segment.edges.map(
  ([from, to], edgeIndex) => ({
    from,
    to,
    accentColor: segment.accentColor,
    segmentIndex,
    edgeIndex,
  }),
));

const BODY_PART_BOX_SPECS = [
  {
    color: BODY_PART_COLORS.head,
    pointNames: ["nose", "left_eye", "right_eye", "left_ear", "right_ear"],
    minPoints: 2,
    padding: 10,
    minWidth: 22,
    minHeight: 20,
  },
  {
    color: BODY_PART_COLORS.torso,
    pointNames: ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    minPoints: 3,
    padding: 12,
    minWidth: 34,
    minHeight: 42,
    requiredGroups: [
      ["left_shoulder", "right_shoulder"],
      ["left_hip", "right_hip"],
    ],
  },
  {
    color: BODY_PART_COLORS.leftArm,
    pointNames: ["left_shoulder", "left_elbow", "left_wrist"],
    minPoints: 2,
    padding: 8,
    minWidth: 18,
    minHeight: 18,
  },
  {
    color: BODY_PART_COLORS.rightArm,
    pointNames: ["right_shoulder", "right_elbow", "right_wrist"],
    minPoints: 2,
    padding: 8,
    minWidth: 18,
    minHeight: 18,
  },
  {
    color: BODY_PART_COLORS.leftLeg,
    pointNames: ["left_hip", "left_knee", "left_ankle"],
    minPoints: 2,
    padding: 8,
    minWidth: 18,
    minHeight: 20,
  },
  {
    color: BODY_PART_COLORS.rightLeg,
    pointNames: ["right_hip", "right_knee", "right_ankle"],
    minPoints: 2,
    padding: 8,
    minWidth: 18,
    minHeight: 20,
  },
];

function drawOverlay(canvas, video, result) {
  const debug = window.__VISION_DEBUG__;
  const mode = debug?.overlayMode || "full";
  const totalStart = performance.now();
  let skeletonMs = 0;
  let bodyBoxMs = 0;
  let highlightMs = 0;

  const rect = video.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  canvas.style.width = `${rect.width}px`;
  canvas.style.height = `${rect.height}px`;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);

  if (mode === "off") {
    overlayStats.record({
      at: Date.now(),
      mode,
      totalMs: performance.now() - totalStart,
      skeletonMs,
      bodyBoxMs,
      highlightMs,
      objects: 0,
    });
    return;
  }

  if (!result || !result.frame_width || !result.frame_height) {
    overlayStats.record({
      at: Date.now(),
      mode,
      totalMs: performance.now() - totalStart,
      skeletonMs,
      bodyBoxMs,
      highlightMs,
      objects: 0,
    });
    return;
  }

  const scale = Math.min(
    rect.width / result.frame_width,
    rect.height / result.frame_height,
  );
  const offsetX = (rect.width - result.frame_width * scale) / 2;
  const offsetY = (rect.height - result.frame_height * scale) / 2;

  ctx.lineWidth = 2;
  ctx.font = "14px Segoe UI, Microsoft YaHei, sans-serif";

  for (const object of result.objects || []) {
    if (!Array.isArray(object?.bbox) || object.bbox.length < 4) {
      continue;
    }

    const bbox = scaleBoundingBox(object.bbox, scale, offsetX, offsetY);
    const poseState = collectPoseState(object, scale, offsetX, offsetY);
    const risk = object.alarm_preview?.risk_level || object.fall_decision?.risk_level || "low";
    const isTarget = object.is_target === true;
    const labelStroke = isTarget ? riskColor(risk) : "#a0a8ad";
    const textColor = isTarget ? "#06120b" : "#dfe7e3";

    drawObjectFrame(ctx, bbox, object, poseState, mode);

    if (mode !== "bbox") {
      const timing = drawPoseOverlay(ctx, object, poseState, mode);
      skeletonMs += timing.skeletonMs;
      bodyBoxMs += timing.bodyBoxMs;
      highlightMs += timing.highlightMs;
    }

    drawObjectLabel(ctx, bbox, object, labelStroke, textColor);
  }

  overlayStats.record({
    at: Date.now(),
    mode,
    totalMs: performance.now() - totalStart,
    skeletonMs,
    bodyBoxMs,
    highlightMs,
    objects: (result.objects || []).length,
  });
}

function drawObjectFrame(ctx, bbox, object, poseState, mode) {
  const isTarget = object.is_target === true;
  const risk = object.alarm_preview?.risk_level || object.fall_decision?.risk_level || "low";
  const color = riskColor(risk);

  if (!isTarget) {
    ctx.save();
    ctx.lineWidth = 1.4;
    ctx.strokeStyle = "rgba(160, 168, 173, 0.52)";
    ctx.fillStyle = "rgba(160, 168, 173, 0.06)";
    fillRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 12);
    strokeRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 12);
    ctx.restore();
    return;
  }

  const usePoseLedHighlight = ENABLE_TARGET_AURA && mode !== "bbox" && poseState?.highlightReady;
  if (usePoseLedHighlight && ENABLE_TARGET_BBOX) {
    ctx.save();
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = withAlpha(color, 0.24);
    ctx.fillStyle = withAlpha(color, 0.05);
    fillRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 16);
    strokeRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 16);
    ctx.restore();
    return;
  }

  ctx.save();
  ctx.lineWidth = 3.2;
  ctx.strokeStyle = withAlpha(color, 0.94);
  ctx.fillStyle = withAlpha(color, 0.12);
  ctx.shadowColor = withAlpha(color, 0.55);
  ctx.shadowBlur = 18;
  fillRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 18);
  strokeRoundedRect(ctx, bbox.x, bbox.y, bbox.width, bbox.height, 18);
  ctx.restore();
}

function drawObjectLabel(ctx, bbox, object, labelStroke, textColor) {
  const isTarget = object.is_target === true;
  const trackLabel = object.track_id == null
    ? object.label
    : isTarget
      ? `Target #${object.track_id}`
      : `Track #${object.track_id}`;
  const identity = object.person_id || "";
  const behavior = localizeOverlayBehavior(object.behavior?.behavior_state);
  const fallPreview = formatFallPreview(object);
  const label = [trackLabel, identity, behavior, fallPreview].filter(Boolean).join(" ");
  const labelWidth = ctx.measureText(label).width + 12;

  ctx.save();
  ctx.fillStyle = labelStroke;
  fillRoundedRect(ctx, bbox.x, Math.max(0, bbox.y - 24), labelWidth, 22, 8);
  ctx.fillStyle = textColor;
  ctx.fillText(label, bbox.x + 6, Math.max(15, bbox.y - 8));
  ctx.restore();
}

function drawPoseOverlay(ctx, object, poseState, mode = "full") {
  const isTarget = object.is_target === true;
  const timing = { skeletonMs: 0, bodyBoxMs: 0, highlightMs: 0 };
  if (!poseState) {
    return timing;
  }

  const drawSkeleton = ENABLE_COLOR_SKELETON && mode !== "bbox";
  const drawBoxes = ENABLE_PART_BOXES && isTarget && mode !== "bbox-skeleton";
  const drawHighlight = ENABLE_TARGET_AURA && isTarget && poseState.highlightReady;

  if (drawHighlight) {
    const startedAt = performance.now();
    drawTargetAura(ctx, poseState, object);
    timing.highlightMs += performance.now() - startedAt;
  }

  if (drawBoxes) {
    const startedAt = performance.now();
    drawBodyPartBoxes(ctx, poseState.points);
    timing.bodyBoxMs += performance.now() - startedAt;
  }

  if (drawSkeleton) {
    const startedAt = performance.now();
    drawRainbowSkeleton(ctx, poseState, object);
    timing.skeletonMs += performance.now() - startedAt;
  }

  return timing;
}

function collectPoseState(object, scale, offsetX, offsetY) {
  if (!object?.pose || !Array.isArray(object.pose.keypoints)) {
    return null;
  }

  const points = new Map();
  for (const kp of object.pose.keypoints) {
    const x = Number(kp?.x);
    const y = Number(kp?.y);
    const confidence = Number(kp?.confidence ?? 0);
    if (!kp?.name || !Number.isFinite(x) || !Number.isFinite(y) || confidence < POSE_CONFIDENCE_THRESHOLD) {
      continue;
    }

    points.set(kp.name, {
      x: x * scale + offsetX,
      y: y * scale + offsetY,
      confidence,
    });
  }

  if (!points.size) {
    return null;
  }

  const pointList = [...points.values()];
  const poseBounds = computeBoundingBox(pointList, {
    padding: 16,
    minWidth: 64,
    minHeight: 120,
  });
  const highlightBounds = poseBounds
    ? expandRect(
      poseBounds,
      Math.max(18, poseBounds.width * 0.08),
      Math.max(22, poseBounds.height * 0.08),
    )
    : null;

  return {
    points,
    pointList,
    poseBounds,
    highlightBounds,
    highlightReady: pointList.length >= 3 && Boolean(highlightBounds),
  };
}

function drawTargetAura(ctx, poseState, object) {
  if (!poseState.highlightBounds) {
    return;
  }

  const risk = object.alarm_preview?.risk_level || object.fall_decision?.risk_level || "low";
  const color = riskColor(risk);
  const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 320);
  const bounds = poseState.highlightBounds;

  ctx.save();
  fillEllipseGradient(ctx, bounds, color, 0.16 + pulse * 0.08, 0.05 + pulse * 0.02);
  ctx.restore();

  if (!ENABLE_TARGET_PULSE) {
    return;
  }

  ctx.save();
  ctx.lineWidth = 2.2 + pulse * 1.3;
  ctx.strokeStyle = withAlpha(color, 0.34 + pulse * 0.2);
  ctx.shadowColor = withAlpha(color, 0.55);
  ctx.shadowBlur = 18 + pulse * 10;
  ctx.setLineDash([18, 12]);
  ctx.lineDashOffset = -performance.now() / 46;
  strokeRoundedRect(ctx, bounds.x, bounds.y, bounds.width, bounds.height, 26);

  ctx.setLineDash([]);
  ctx.lineWidth = 1.1;
  ctx.shadowBlur = 0;
  ctx.strokeStyle = withAlpha("#ffffff", 0.2 + pulse * 0.06);
  strokeRoundedRect(
    ctx,
    bounds.x + 7,
    bounds.y + 7,
    Math.max(0, bounds.width - 14),
    Math.max(0, bounds.height - 14),
    20,
  );
  ctx.restore();
}

function drawRainbowSkeleton(ctx, poseState, object) {
  const isTarget = object.is_target === true;
  const risk = object.alarm_preview?.risk_level || object.fall_decision?.risk_level || "low";
  const focusColor = riskColor(risk);
  const visibleEdges = collectVisibleEdges(poseState.points);
  if (!visibleEdges.length) {
    return;
  }

  const lineWidth = computeSkeletonLineWidth(poseState.poseBounds, isTarget);
  const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 420);
  const edgeAlpha = isTarget ? 0.96 : 0.38;
  const keypointRadius = clamp(lineWidth * 0.58, 3, 5.8);

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  if (isTarget) {
    ctx.lineWidth = lineWidth * 2.15;
    ctx.strokeStyle = withAlpha(focusColor, 0.16 + pulse * 0.06);
    for (const edge of visibleEdges) {
      strokeLine(ctx, edge.a, edge.b);
    }
  }

  ctx.lineWidth = lineWidth;
  visibleEdges.forEach((edge, index) => {
    ctx.strokeStyle = createRainbowGradient(
      ctx,
      edge.a,
      edge.b,
      index,
      visibleEdges.length,
      edgeAlpha,
    );
    strokeLine(ctx, edge.a, edge.b);
  });

  if (isTarget) {
    ctx.lineWidth = Math.max(1.2, lineWidth * 0.24);
    ctx.strokeStyle = withAlpha("#ffffff", 0.28);
    for (const edge of visibleEdges) {
      strokeLine(ctx, edge.a, edge.b);
    }
  }

  ctx.shadowBlur = isTarget ? 10 : 0;
  ctx.shadowColor = isTarget ? withAlpha(focusColor, 0.42) : "transparent";
  ctx.fillStyle = withAlpha(BODY_PART_COLORS.keypoint, isTarget ? 0.98 : 0.78);
  ctx.strokeStyle = withAlpha(BODY_PART_COLORS.keypointStroke, isTarget ? 0.64 : 0.44);
  ctx.lineWidth = 1.1;

  for (const point of poseState.pointList) {
    ctx.beginPath();
    ctx.arc(point.x, point.y, keypointRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  ctx.restore();
}

function drawBodyPartBoxes(ctx, points) {
  ctx.save();
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  for (const spec of BODY_PART_BOX_SPECS) {
    if (!shouldRenderPartBox(spec, points)) {
      continue;
    }

    const boxPoints = spec.pointNames.map((name) => points.get(name)).filter(Boolean);
    const box = computeBoundingBox(boxPoints, spec);
    if (!box) {
      continue;
    }

    ctx.strokeStyle = withAlpha(spec.color, 0.7);
    ctx.shadowColor = withAlpha(spec.color, 0.24);
    ctx.shadowBlur = 8;
    strokeRoundedRect(ctx, box.x, box.y, box.width, box.height, 10);
  }

  ctx.restore();
}

function shouldRenderPartBox(spec, points) {
  const availableCount = spec.pointNames.reduce(
    (count, name) => count + (points.has(name) ? 1 : 0),
    0,
  );
  if (availableCount < spec.minPoints) {
    return false;
  }

  if (!spec.requiredGroups) {
    return true;
  }

  return spec.requiredGroups.every((group) => group.some((name) => points.has(name)));
}

function collectVisibleEdges(points) {
  const edges = [];
  for (const edge of SKELETON_EDGES) {
    const a = points.get(edge.from);
    const b = points.get(edge.to);
    if (!a || !b) {
      continue;
    }
    edges.push({ ...edge, a, b });
  }
  return edges;
}

function scaleBoundingBox(bbox, scale, offsetX, offsetY) {
  const [x1, y1, x2, y2] = bbox;
  return {
    x: x1 * scale + offsetX,
    y: y1 * scale + offsetY,
    width: (x2 - x1) * scale,
    height: (y2 - y1) * scale,
  };
}

function computeBoundingBox(points, options = {}) {
  if (!points.length) {
    return null;
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const point of points) {
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x);
    maxY = Math.max(maxY, point.y);
  }

  if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
    return null;
  }

  const padding = options.padding ?? 8;
  const minWidth = options.minWidth ?? 16;
  const minHeight = options.minHeight ?? 16;
  const width = maxX - minX;
  const height = maxY - minY;
  const extraWidth = Math.max(0, minWidth - width) / 2;
  const extraHeight = Math.max(0, minHeight - height) / 2;

  return {
    x: minX - padding - extraWidth,
    y: minY - padding - extraHeight,
    width: width + padding * 2 + extraWidth * 2,
    height: height + padding * 2 + extraHeight * 2,
  };
}

function expandRect(rect, paddingX, paddingY = paddingX) {
  return {
    x: rect.x - paddingX,
    y: rect.y - paddingY,
    width: rect.width + paddingX * 2,
    height: rect.height + paddingY * 2,
  };
}

function computeSkeletonLineWidth(bounds, isTarget) {
  const span = Math.max(bounds?.height ?? 0, bounds?.width ?? 0, 96);
  if (isTarget) {
    return clamp(span / 42, 4, 8);
  }
  return clamp(span / 58, 2.4, 4.6);
}

function createRainbowGradient(ctx, from, to, index, total, alpha) {
  const gradient = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
  const phase = performance.now() / 32;
  const baseHue = (phase + (index / Math.max(total, 1)) * 360) % 360;
  gradient.addColorStop(0, hsla(baseHue, 98, 62, alpha));
  gradient.addColorStop(0.5, hsla((baseHue + 78) % 360, 100, 68, alpha));
  gradient.addColorStop(1, hsla((baseHue + 156) % 360, 98, 62, alpha));
  return gradient;
}

function fillEllipseGradient(ctx, bounds, color, innerAlpha, outerAlpha) {
  const centerX = bounds.x + bounds.width / 2;
  const centerY = bounds.y + bounds.height / 2;
  const radiusX = Math.max(1, bounds.width / 2);
  const radiusY = Math.max(1, bounds.height / 2);
  const radial = ctx.createRadialGradient(
    centerX,
    centerY,
    Math.max(1, Math.min(radiusX, radiusY) * 0.18),
    centerX,
    centerY,
    Math.max(radiusX, radiusY),
  );

  radial.addColorStop(0, withAlpha(color, innerAlpha));
  radial.addColorStop(0.58, withAlpha(color, outerAlpha));
  radial.addColorStop(1, withAlpha(color, 0));

  ctx.fillStyle = radial;
  ctx.beginPath();
  ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, Math.PI * 2);
  ctx.fill();
}

function strokeLine(ctx, from, to) {
  ctx.beginPath();
  ctx.moveTo(from.x, from.y);
  ctx.lineTo(to.x, to.y);
  ctx.stroke();
}

function strokeRoundedRect(ctx, x, y, width, height, radius) {
  if (width <= 0 || height <= 0) {
    return;
  }
  traceRoundedRect(ctx, x, y, width, height, radius);
  ctx.stroke();
}

function fillRoundedRect(ctx, x, y, width, height, radius) {
  if (width <= 0 || height <= 0) {
    return;
  }
  traceRoundedRect(ctx, x, y, width, height, radius);
  ctx.fill();
}

function traceRoundedRect(ctx, x, y, width, height, radius) {
  const safeRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
  ctx.beginPath();

  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, width, height, safeRadius);
    return;
  }

  ctx.moveTo(x + safeRadius, y);
  ctx.lineTo(x + width - safeRadius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  ctx.lineTo(x + width, y + height - safeRadius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - safeRadius, y + height);
  ctx.lineTo(x + safeRadius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  ctx.lineTo(x, y + safeRadius);
  ctx.quadraticCurveTo(x, y, x + safeRadius, y);
}

function withAlpha(hexColor, alpha) {
  const hex = hexColor.replace("#", "");
  const expanded = hex.length === 3
    ? hex.split("").map((char) => `${char}${char}`).join("")
    : hex;

  if (expanded.length !== 6) {
    return hexColor;
  }

  const red = parseInt(expanded.slice(0, 2), 16);
  const green = parseInt(expanded.slice(2, 4), 16);
  const blue = parseInt(expanded.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${clamp(alpha, 0, 1)})`;
}

function hsla(hue, saturation, lightness, alpha) {
  return `hsla(${Math.round(hue)}, ${saturation}%, ${lightness}%, ${clamp(alpha, 0, 1)})`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function statAverage(values) {
  if (!values.length) {
    return null;
  }
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100;
}

function statMax(values) {
  if (!values.length) {
    return null;
  }
  return Math.round(Math.max(...values) * 100) / 100;
}

window.drawOverlay = drawOverlay;

function formatFallPreview(object) {
  const probability = object.temporal?.fall_probability;
  const state = object.fall_decision?.fall_state;
  if (!state) {
    return "";
  }
  if (state === "falling") {
    const percent = formatProbabilityPercent(probability);
    return percent ? `${OVERLAY_FALL_STATE_LABELS[state]} ${percent}` : OVERLAY_FALL_STATE_LABELS[state];
  }
  return OVERLAY_FALL_STATE_LABELS[state] || state;
}

function localizeOverlayBehavior(value) {
  return OVERLAY_BEHAVIOR_LABELS[value] || value || "";
}

function formatProbabilityPercent(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "";
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function riskColor(risk) {
  const colors = {
    low: "#72e58f",
    medium: "#f4d35e",
    high: "#ff9f43",
    critical: "#ff4d4f",
    cooldown: "#9aa4aa",
  };
  return colors[risk] || colors.low;
}

function riskFill(risk) {
  const fills = {
    low: "rgba(114, 229, 143, 0.18)",
    medium: "rgba(244, 211, 94, 0.2)",
    high: "rgba(255, 159, 67, 0.22)",
    critical: "rgba(255, 77, 79, 0.25)",
    cooldown: "rgba(154, 164, 170, 0.18)",
  };
  return fills[risk] || fills.low;
}
