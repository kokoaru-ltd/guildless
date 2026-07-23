// NEON DRIFT — deterministic, pure game rules.
//
// Every function here is a pure mapping from inputs to outputs: no Date, no
// module state, and no Math.random (randomness is injected as a `rand`
// argument). App.tsx owns the clock, the render loop, and the touch input;
// this module owns the math, so Node's built-in test runner can verify the
// game exactly (see gameRules.test.mjs).
'use strict';

// ---------------------------------------------------------------------------
// Approved tuning constants
// ---------------------------------------------------------------------------
const GAME_DURATION_MS = 60000;
const MAX_HEALTH = 3;
const COMBO_CAP = 10;
const COMBO_WINDOW_MS = 2500;
const INVULN_MS = 1200;
const SHARD_BASE_SCORE = 10;
const DT_CLAMP_MS = 33;

// Mine population ramps up over the run: base count, +1 every interval,
// hard-capped so late game stays fair on small screens.
const MINE_BASE_COUNT = 3;
const MINE_MAX_COUNT = 7;
const MINE_RAMP_INTERVAL_MS = 12000;

// Mine drift speed (px/second) scales linearly from min at 0:00 to max at 1:00.
const MINE_SPEED_MIN = 70;
const MINE_SPEED_MAX = 165;

// New mines never materialize within this distance of the player.
const MINE_SAFE_DISTANCE = 130;

// New shards keep enough clearance that they are never collected on the same
// frame they appear (must exceed PLAYER_RADIUS + SHARD_RADIUS).
const SHARD_SAFE_DISTANCE = 60;

// Spawn rolls drawn from `rand` before falling back to the farthest corner.
const SPAWN_ATTEMPTS = 8;

// Collision radii (px) and spawn padding from the arena edges.
const PLAYER_RADIUS = 17;
const SHARD_RADIUS = 12;
const MINE_RADIUS = 15;
const SHARD_TARGET_COUNT = 3;
const SPAWN_MARGIN = 26;

// Exponential smoothing constant (per ms) for the orb chasing the thumb.
const PLAYER_FOLLOW_RATE = 0.016;

// ---------------------------------------------------------------------------
// Clock
// ---------------------------------------------------------------------------

/** Clamp a raw requestAnimationFrame delta. Non-finite or negative -> 0. */
function clampDelta(dtMs) {
  if (!Number.isFinite(dtMs) || dtMs <= 0) return 0;
  return Math.min(dtMs, DT_CLAMP_MS);
}

/**
 * Clamp a raw frame delta for the authoritative gameplay clock. Unlike
 * clampDelta this preserves real wall-clock time on slow frames, so the
 * 60-second run lasts 60 real seconds even at low frame rates. App lifecycle
 * code resets the timestamp on resume, so background time is excluded there.
 */
function clampElapsedDelta(dtMs) {
  if (!Number.isFinite(dtMs) || dtMs <= 0) return 0;
  return dtMs;
}

function timeLeftMs(elapsedMs) {
  return Math.max(0, GAME_DURATION_MS - elapsedMs);
}

/** Countdown as shown on the HUD: 60 at start, 0 exactly when time is up. */
function secondsLeft(elapsedMs) {
  return Math.ceil(timeLeftMs(elapsedMs) / 1000);
}

function isTimeUp(elapsedMs) {
  return elapsedMs >= GAME_DURATION_MS;
}

// ---------------------------------------------------------------------------
// Run state: score, combo, health
// ---------------------------------------------------------------------------

/** Fresh run. Starts with a brief invulnerability grace so spawns are fair. */
function createRunState() {
  return {
    elapsedMs: 0,
    score: 0,
    combo: 1,
    comboExpiresAtMs: -1,
    health: MAX_HEALTH,
    invulnerableUntilMs: INVULN_MS,
  };
}

function isComboActive(run, nowMs) {
  return nowMs <= run.comboExpiresAtMs;
}

/** 1 -> window just refreshed, 0 -> expired. Drives the HUD combo meter. */
function comboWindowFraction(run, nowMs) {
  if (!isComboActive(run, nowMs)) return 0;
  return Math.min(1, (run.comboExpiresAtMs - nowMs) / COMBO_WINDOW_MS);
}

/**
 * Collect one shard at `nowMs`. Chaining within the combo window raises the
 * multiplier (capped); letting it lapse resets to x1. Score gain is
 * SHARD_BASE_SCORE * multiplier after the chain step.
 */
function collectShard(run, nowMs) {
  const combo = isComboActive(run, nowMs) ? Math.min(run.combo + 1, COMBO_CAP) : 1;
  const gained = SHARD_BASE_SCORE * combo;
  return {
    run: {
      ...run,
      score: run.score + gained,
      combo,
      comboExpiresAtMs: nowMs + COMBO_WINDOW_MS,
    },
    gained,
  };
}

function isInvulnerable(run, nowMs) {
  return nowMs < run.invulnerableUntilMs;
}

/**
 * Touch a mine at `nowMs`. Ignored while invulnerable (or already dead);
 * otherwise costs one heart and grants a fresh invulnerability window.
 */
function hitMine(run, nowMs) {
  if (isInvulnerable(run, nowMs) || run.health <= 0) {
    return { run, tookDamage: false };
  }
  return {
    run: { ...run, health: run.health - 1, invulnerableUntilMs: nowMs + INVULN_MS },
    tookDamage: true,
  };
}

function isGameOver(run) {
  return run.health <= 0 || isTimeUp(run.elapsedMs);
}

// ---------------------------------------------------------------------------
// Difficulty ramp
// ---------------------------------------------------------------------------

function mineCountForElapsed(elapsedMs) {
  const steps = Math.floor(Math.max(0, elapsedMs) / MINE_RAMP_INTERVAL_MS);
  return Math.min(MINE_MAX_COUNT, MINE_BASE_COUNT + steps);
}

function mineSpeedForElapsed(elapsedMs) {
  const t = Math.min(1, Math.max(0, elapsedMs / GAME_DURATION_MS));
  return MINE_SPEED_MIN + (MINE_SPEED_MAX - MINE_SPEED_MIN) * t;
}

// ---------------------------------------------------------------------------
// Geometry and motion
// ---------------------------------------------------------------------------

function circlesOverlap(ax, ay, ar, bx, by, br) {
  const dx = ax - bx;
  const dy = ay - by;
  const rr = ar + br;
  return dx * dx + dy * dy < rr * rr;
}

function clampToBounds(x, y, r, bounds) {
  return {
    x: Math.min(Math.max(x, r), Math.max(r, bounds.width - r)),
    y: Math.min(Math.max(y, r), Math.max(r, bounds.height - r)),
  };
}

/**
 * Move the player orb toward the thumb target with framerate-independent
 * exponential smoothing. Never overshoots; dt of 0 is a no-op.
 */
function stepPlayer(pos, target, dtMs) {
  const blend = 1 - Math.exp(-Math.max(0, dtMs) * PLAYER_FOLLOW_RATE);
  return {
    x: pos.x + (target.x - pos.x) * blend,
    y: pos.y + (target.y - pos.y) * blend,
  };
}

/** Advance a mine by dt, reflecting off arena walls. */
function stepMine(mine, dtMs, bounds) {
  const dt = Math.max(0, dtMs) / 1000;
  let x = mine.x + mine.vx * dt;
  let y = mine.y + mine.vy * dt;
  let vx = mine.vx;
  let vy = mine.vy;
  const maxX = Math.max(mine.r, bounds.width - mine.r);
  const maxY = Math.max(mine.r, bounds.height - mine.r);
  if (x < mine.r) {
    x = mine.r + (mine.r - x);
    vx = -vx;
  } else if (x > maxX) {
    x = maxX - (x - maxX);
    vx = -vx;
  }
  if (y < mine.r) {
    y = mine.r + (mine.r - y);
    vy = -vy;
  } else if (y > maxY) {
    y = maxY - (y - maxY);
    vy = -vy;
  }
  x = Math.min(Math.max(x, mine.r), maxX);
  y = Math.min(Math.max(y, mine.r), maxY);
  return { ...mine, x, y, vx, vy, phase: mine.phase + dtMs * 0.006 };
}

// ---------------------------------------------------------------------------
// Spawning (deterministic given the injected rand function)
// ---------------------------------------------------------------------------

function spawnPoint(rand, bounds, margin) {
  return {
    x: margin + rand() * Math.max(0, bounds.width - margin * 2),
    y: margin + rand() * Math.max(0, bounds.height - margin * 2),
  };
}

/**
 * Roll a spawn point at least `safeDistance` away from `avoid`. Draws up to
 * SPAWN_ATTEMPTS candidates from `rand` (still deterministic given the
 * sequence), then falls back to the corner of the spawn rectangle farthest
 * from `avoid`. The distance-maximizing point of an axis-aligned rectangle
 * is always one of its corners, so the fallback is the mathematically best
 * position that exists — it honors `safeDistance` whenever any point in the
 * rectangle can, and degrades to the farthest reachable point on arenas too
 * small to honor it at all.
 */
function spawnPointAway(rand, bounds, margin, avoid, safeDistance) {
  const safeSq = safeDistance * safeDistance;
  for (let i = 0; i < SPAWN_ATTEMPTS; i += 1) {
    const p = spawnPoint(rand, bounds, margin);
    const dx = p.x - avoid.x;
    const dy = p.y - avoid.y;
    if (dx * dx + dy * dy >= safeSq) return p;
  }
  const minX = margin;
  const maxX = Math.max(margin, bounds.width - margin);
  const minY = margin;
  const maxY = Math.max(margin, bounds.height - margin);
  return {
    x: avoid.x - minX >= maxX - avoid.x ? minX : maxX,
    y: avoid.y - minY >= maxY - avoid.y ? minY : maxY,
  };
}

/**
 * Spawn a shard. When `avoid` (the player) is given, the shard is guaranteed
 * at least SHARD_SAFE_DISTANCE away so it can never appear pre-collected
 * under the orb.
 */
function spawnShard(rand, bounds, avoid) {
  const margin = SPAWN_MARGIN + SHARD_RADIUS;
  const p = avoid
    ? spawnPointAway(rand, bounds, margin, avoid, SHARD_SAFE_DISTANCE)
    : spawnPoint(rand, bounds, margin);
  return { x: p.x, y: p.y, r: SHARD_RADIUS, phase: rand() * Math.PI * 2 };
}

/**
 * Spawn a mine with a drift velocity scaled to the elapsed-time difficulty.
 * When `avoid` (the player) is given, the position is guaranteed at least
 * MINE_SAFE_DISTANCE away wherever the arena admits such a point (see
 * spawnPointAway).
 */
function spawnMine(rand, bounds, elapsedMs, avoid) {
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  const p = avoid
    ? spawnPointAway(rand, bounds, margin, avoid, MINE_SAFE_DISTANCE)
    : spawnPoint(rand, bounds, margin);
  const speed = mineSpeedForElapsed(elapsedMs);
  const angle = rand() * Math.PI * 2;
  return {
    x: p.x,
    y: p.y,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    r: MINE_RADIUS,
    phase: rand() * Math.PI * 2,
  };
}

module.exports = {
  GAME_DURATION_MS,
  MAX_HEALTH,
  COMBO_CAP,
  COMBO_WINDOW_MS,
  INVULN_MS,
  SHARD_BASE_SCORE,
  DT_CLAMP_MS,
  MINE_BASE_COUNT,
  MINE_MAX_COUNT,
  MINE_RAMP_INTERVAL_MS,
  MINE_SPEED_MIN,
  MINE_SPEED_MAX,
  MINE_SAFE_DISTANCE,
  SHARD_SAFE_DISTANCE,
  SPAWN_ATTEMPTS,
  PLAYER_RADIUS,
  SHARD_RADIUS,
  MINE_RADIUS,
  SHARD_TARGET_COUNT,
  SPAWN_MARGIN,
  PLAYER_FOLLOW_RATE,
  clampDelta,
  clampElapsedDelta,
  timeLeftMs,
  secondsLeft,
  isTimeUp,
  createRunState,
  isComboActive,
  comboWindowFraction,
  collectShard,
  isInvulnerable,
  hitMine,
  isGameOver,
  mineCountForElapsed,
  mineSpeedForElapsed,
  circlesOverlap,
  clampToBounds,
  stepPlayer,
  stepMine,
  spawnShard,
  spawnMine,
};
