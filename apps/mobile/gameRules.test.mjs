// NEON DRIFT rules tests — run with `npm test` (Node's built-in test runner).
import test from 'node:test';
import assert from 'node:assert/strict';

import rules from './gameRules.js';

const {
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
  SPAWN_MARGIN,
  PLAYER_RADIUS,
  SHARD_RADIUS,
  MINE_RADIUS,
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
} = rules;

const BOUNDS = { width: 390, height: 700 };

/** Deterministic stand-in for Math.random: cycles through the given values. */
function seq(...values) {
  let i = 0;
  return () => values[i++ % values.length];
}

/** Deterministic LCG in [0, 1) for property-style sweeps. */
function lcg(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

/** Grid of player positions covering corners, edges, and the exact center. */
function playerGrid(bounds) {
  const positions = [];
  for (const fx of [0, 0.25, 0.5, 0.75, 1]) {
    for (const fy of [0, 0.25, 0.5, 0.75, 1]) {
      positions.push({ x: fx * bounds.width, y: fy * bounds.height });
    }
  }
  return positions;
}

/** A rand() that maps every spawn roll as close to `player` as [0,1] allows. */
function adversarialRand(player, bounds, margin) {
  const span = (size) => Math.max(0, size - margin * 2);
  const rx = span(bounds.width) > 0 ? Math.min(1, Math.max(0, (player.x - margin) / span(bounds.width))) : 0;
  const ry = span(bounds.height) > 0 ? Math.min(1, Math.max(0, (player.y - margin) / span(bounds.height))) : 0;
  return seq(rx, ry);
}

/** Farthest distance from `p` achievable inside the spawn rectangle. */
function farthestPossible(p, bounds, margin) {
  const maxX = Math.max(margin, bounds.width - margin);
  const maxY = Math.max(margin, bounds.height - margin);
  let best = 0;
  for (const cx of [margin, maxX]) {
    for (const cy of [margin, maxY]) {
      best = Math.max(best, Math.hypot(cx - p.x, cy - p.y));
    }
  }
  return best;
}

test('approved tuning constants', () => {
  assert.equal(GAME_DURATION_MS, 60000);
  assert.equal(MAX_HEALTH, 3);
  assert.equal(COMBO_CAP, 10);
  assert.equal(COMBO_WINDOW_MS, 2500);
  assert.equal(INVULN_MS, 1200);
  assert.equal(SHARD_BASE_SCORE, 10);
  assert.equal(DT_CLAMP_MS, 33);
  assert.equal(SPAWN_ATTEMPTS, 8);
  // A freshly spawned shard must never be collected on its spawn frame.
  assert.ok(SHARD_SAFE_DISTANCE > PLAYER_RADIUS + SHARD_RADIUS);
});

test('clampDelta clamps frame spikes and rejects garbage', () => {
  assert.equal(clampDelta(16.7), 16.7);
  assert.equal(clampDelta(33), 33);
  assert.equal(clampDelta(250), DT_CLAMP_MS); // resume after a long stall
  assert.equal(clampDelta(0), 0);
  assert.equal(clampDelta(-5), 0);
  assert.equal(clampDelta(NaN), 0);
  assert.equal(clampDelta(Infinity), 0);
});

test('clampElapsedDelta preserves authoritative wall-clock time', () => {
  assert.equal(clampElapsedDelta(16.7), 16.7);
  // Slow frames beyond the physics clamp still count at full wall-clock value.
  assert.equal(clampElapsedDelta(50), 50);
  assert.equal(clampElapsedDelta(DT_CLAMP_MS + 1), DT_CLAMP_MS + 1);
  assert.equal(clampElapsedDelta(250), 250);
  assert.equal(clampElapsedDelta(5000), 5000);
  assert.equal(clampElapsedDelta(0), 0);
  assert.equal(clampElapsedDelta(-5), 0);
  assert.equal(clampElapsedDelta(NaN), 0);
  assert.equal(clampElapsedDelta(Infinity), 0);
});

test('gameplay clock: a 20fps run ends after exactly 60 wall-seconds', () => {
  // Regression: elapsed used to advance by the clamped physics delta, so a
  // 50ms-frame device stretched the "60 second" run to ~91 wall-seconds.
  const frameMs = 50;
  let elapsed = 0;
  let physicsMs = 0;
  let frames = 0;
  while (!isTimeUp(elapsed)) {
    elapsed += clampElapsedDelta(frameMs);
    physicsMs += clampDelta(frameMs);
    frames += 1;
    assert.ok(frames <= 1200, 'timer must not run slower than the wall clock');
  }
  assert.equal(frames * frameMs, GAME_DURATION_MS);
  // Physics stays clamped (no tunneling), independent of the timer.
  assert.equal(physicsMs, frames * DT_CLAMP_MS);
});

test('timer: timeLeftMs / secondsLeft / isTimeUp', () => {
  assert.equal(timeLeftMs(0), 60000);
  assert.equal(secondsLeft(0), 60);
  assert.equal(secondsLeft(500), 60);
  assert.equal(secondsLeft(59001), 1);
  assert.equal(secondsLeft(60000), 0);
  assert.equal(timeLeftMs(75000), 0);
  assert.equal(isTimeUp(59999), false);
  assert.equal(isTimeUp(60000), true);
});

test('createRunState starts full-health with spawn grace', () => {
  const run = createRunState();
  assert.equal(run.elapsedMs, 0);
  assert.equal(run.score, 0);
  assert.equal(run.combo, 1);
  assert.equal(run.health, MAX_HEALTH);
  assert.equal(run.invulnerableUntilMs, INVULN_MS);
  assert.equal(isInvulnerable(run, 0), true);
  assert.equal(isInvulnerable(run, INVULN_MS), false);
  assert.equal(isComboActive(run, 0), false);
});

test('collectShard: first shard scores base at x1', () => {
  const start = createRunState();
  const { run, gained } = collectShard(start, 1000);
  assert.equal(gained, SHARD_BASE_SCORE);
  assert.equal(run.score, SHARD_BASE_SCORE);
  assert.equal(run.combo, 1);
  assert.equal(run.comboExpiresAtMs, 1000 + COMBO_WINDOW_MS);
  // Purity: the input state must not be mutated.
  assert.equal(start.score, 0);
  assert.equal(start.comboExpiresAtMs, -1);
});

test('collectShard: chaining inside the window ramps the multiplier', () => {
  let run = createRunState();
  let gained;
  ({ run, gained } = collectShard(run, 1000));
  assert.equal(gained, 10);
  ({ run, gained } = collectShard(run, 2000)); // inside window -> x2
  assert.equal(gained, 20);
  ({ run, gained } = collectShard(run, 2000 + COMBO_WINDOW_MS)); // boundary counts -> x3
  assert.equal(gained, 30);
  assert.equal(run.score, 60);
  assert.equal(run.combo, 3);
});

test('collectShard: multiplier caps at COMBO_CAP', () => {
  let run = createRunState();
  let now = 0;
  for (let i = 0; i < 15; i += 1) {
    now += 100;
    ({ run } = collectShard(run, now));
  }
  assert.equal(run.combo, COMBO_CAP);
  const { gained } = collectShard(run, now + 100);
  assert.equal(gained, SHARD_BASE_SCORE * COMBO_CAP);
});

test('collectShard: lapsed window resets to x1', () => {
  let run = createRunState();
  ({ run } = collectShard(run, 1000));
  ({ run } = collectShard(run, 1500));
  assert.equal(run.combo, 2);
  const late = 1500 + COMBO_WINDOW_MS + 1;
  assert.equal(isComboActive(run, late), false);
  const { run: next, gained } = collectShard(run, late);
  assert.equal(next.combo, 1);
  assert.equal(gained, SHARD_BASE_SCORE);
});

test('comboWindowFraction drains from 1 to 0', () => {
  let run = createRunState();
  ({ run } = collectShard(run, 1000));
  assert.equal(comboWindowFraction(run, 1000), 1);
  assert.equal(comboWindowFraction(run, 1000 + COMBO_WINDOW_MS / 2), 0.5);
  assert.equal(comboWindowFraction(run, 1000 + COMBO_WINDOW_MS), 0);
  assert.equal(comboWindowFraction(run, 9999), 0);
});

test('hitMine: costs a heart and grants invulnerability', () => {
  const start = { ...createRunState(), invulnerableUntilMs: 0 };
  const { run, tookDamage } = hitMine(start, 5000);
  assert.equal(tookDamage, true);
  assert.equal(run.health, MAX_HEALTH - 1);
  assert.equal(run.invulnerableUntilMs, 5000 + INVULN_MS);
  assert.equal(start.health, MAX_HEALTH); // purity
});

test('hitMine: ignored while invulnerable, active again at the boundary', () => {
  const start = { ...createRunState(), invulnerableUntilMs: 0 };
  const first = hitMine(start, 5000);
  const during = hitMine(first.run, 5000 + INVULN_MS - 1);
  assert.equal(during.tookDamage, false);
  assert.equal(during.run.health, first.run.health);
  const after = hitMine(first.run, 5000 + INVULN_MS);
  assert.equal(after.tookDamage, true);
  assert.equal(after.run.health, MAX_HEALTH - 2);
});

test('hitMine: never drops health below zero', () => {
  let run = { ...createRunState(), invulnerableUntilMs: 0 };
  let now = 0;
  for (let i = 0; i < 5; i += 1) {
    now += INVULN_MS + 1000;
    ({ run } = hitMine(run, now));
  }
  assert.equal(run.health, 0);
  const extra = hitMine(run, now + INVULN_MS + 1000);
  assert.equal(extra.tookDamage, false);
  assert.equal(extra.run.health, 0);
});

test('isGameOver: on zero health or time up, not mid-run', () => {
  const run = createRunState();
  assert.equal(isGameOver({ ...run, elapsedMs: 30000 }), false);
  assert.equal(isGameOver({ ...run, health: 0 }), true);
  assert.equal(isGameOver({ ...run, elapsedMs: GAME_DURATION_MS }), true);
});

test('mineCountForElapsed ramps by interval and caps', () => {
  assert.equal(mineCountForElapsed(0), MINE_BASE_COUNT);
  assert.equal(mineCountForElapsed(MINE_RAMP_INTERVAL_MS - 1), MINE_BASE_COUNT);
  assert.equal(mineCountForElapsed(MINE_RAMP_INTERVAL_MS), MINE_BASE_COUNT + 1);
  assert.equal(mineCountForElapsed(GAME_DURATION_MS), MINE_MAX_COUNT);
  assert.equal(mineCountForElapsed(GAME_DURATION_MS * 10), MINE_MAX_COUNT);
  let prev = 0;
  for (let t = 0; t <= GAME_DURATION_MS; t += 1000) {
    const count = mineCountForElapsed(t);
    assert.ok(count >= prev, `count must never decrease (t=${t})`);
    prev = count;
  }
});

test('mineSpeedForElapsed scales linearly and clamps', () => {
  assert.equal(mineSpeedForElapsed(0), MINE_SPEED_MIN);
  assert.equal(mineSpeedForElapsed(GAME_DURATION_MS), MINE_SPEED_MAX);
  assert.equal(mineSpeedForElapsed(GAME_DURATION_MS * 2), MINE_SPEED_MAX);
  assert.equal(mineSpeedForElapsed(-500), MINE_SPEED_MIN);
  const mid = mineSpeedForElapsed(GAME_DURATION_MS / 2);
  assert.equal(mid, (MINE_SPEED_MIN + MINE_SPEED_MAX) / 2);
});

test('circlesOverlap: strict overlap, touching is not a hit', () => {
  assert.equal(circlesOverlap(0, 0, 10, 15, 0, 10), true);
  assert.equal(circlesOverlap(0, 0, 10, 20, 0, 10), false); // exactly touching
  assert.equal(circlesOverlap(0, 0, 10, 21, 0, 10), false);
  assert.equal(circlesOverlap(3, 4, 3, 0, 0, 3), true); // distance 5 < 6
});

test('clampToBounds keeps a circle fully inside the arena', () => {
  assert.deepEqual(clampToBounds(-50, 350, 17, BOUNDS), { x: 17, y: 350 });
  assert.deepEqual(clampToBounds(9999, 9999, 17, BOUNDS), {
    x: BOUNDS.width - 17,
    y: BOUNDS.height - 17,
  });
  assert.deepEqual(clampToBounds(200, 300, 17, BOUNDS), { x: 200, y: 300 });
});

test('stepPlayer: converges to the target without overshooting', () => {
  const target = { x: 300, y: 500 };
  let pos = { x: 100, y: 100 };
  let lastDist = Math.hypot(target.x - pos.x, target.y - pos.y);
  for (let i = 0; i < 240; i += 1) {
    pos = stepPlayer(pos, target, 16.7);
    const dist = Math.hypot(target.x - pos.x, target.y - pos.y);
    assert.ok(dist <= lastDist, 'distance to target must never grow');
    lastDist = dist;
  }
  assert.ok(lastDist < 0.5, 'orb reaches the thumb after ~4 seconds');
  // dt = 0 is a no-op; identical inputs give identical outputs.
  assert.deepEqual(stepPlayer({ x: 5, y: 5 }, target, 0), { x: 5, y: 5 });
  assert.deepEqual(stepPlayer({ x: 5, y: 5 }, target, 16), stepPlayer({ x: 5, y: 5 }, target, 16));
});

test('stepMine: straight drift matches velocity * dt', () => {
  const mine = { x: 100, y: 100, vx: 60, vy: -30, r: MINE_RADIUS, phase: 0 };
  const next = stepMine(mine, 1000, BOUNDS);
  assert.equal(next.x, 160);
  assert.equal(next.y, 70);
  assert.equal(next.vx, 60);
  assert.equal(next.vy, -30);
  assert.ok(next.phase > 0);
  assert.equal(mine.x, 100); // purity
});

test('stepMine: reflects off walls and flips velocity', () => {
  const mine = { x: MINE_RADIUS + 5, y: 300, vx: -100, vy: 0, r: MINE_RADIUS, phase: 0 };
  const next = stepMine(mine, 200, BOUNDS); // tries to move 20px past its 5px gap
  assert.equal(next.vx, 100);
  assert.equal(next.x, MINE_RADIUS + 15); // mirrored around the wall
  const right = stepMine(
    { x: BOUNDS.width - MINE_RADIUS - 2, y: 300, vx: 100, vy: 0, r: MINE_RADIUS, phase: 0 },
    100,
    BOUNDS,
  );
  assert.equal(right.vx, -100);
  assert.ok(right.x <= BOUNDS.width - MINE_RADIUS);
});

test('stepMine: stays in bounds through a full simulated run', () => {
  let mine = { x: 50, y: 60, vx: 143, vy: -117, r: MINE_RADIUS, phase: 0 };
  for (let t = 0; t < GAME_DURATION_MS; t += 16) {
    mine = stepMine(mine, 16, BOUNDS);
    assert.ok(mine.x >= MINE_RADIUS && mine.x <= BOUNDS.width - MINE_RADIUS, `x in bounds at t=${t}`);
    assert.ok(mine.y >= MINE_RADIUS && mine.y <= BOUNDS.height - MINE_RADIUS, `y in bounds at t=${t}`);
  }
});

test('spawnShard: deterministic and inside spawn margins', () => {
  const margin = SPAWN_MARGIN + SHARD_RADIUS;
  const a = spawnShard(seq(0, 0, 0), BOUNDS);
  assert.deepEqual({ x: a.x, y: a.y }, { x: margin, y: margin });
  const b = spawnShard(seq(1, 1, 1), BOUNDS);
  assert.deepEqual({ x: b.x, y: b.y }, { x: BOUNDS.width - margin, y: BOUNDS.height - margin });
  const c1 = spawnShard(seq(0.25, 0.75, 0.5), BOUNDS);
  const c2 = spawnShard(seq(0.25, 0.75, 0.5), BOUNDS);
  assert.deepEqual(c1, c2);
});

test('spawnMine: speed follows the difficulty ramp', () => {
  const early = spawnMine(seq(0.5, 0.5, 0, 0), BOUNDS, 0);
  assert.ok(Math.abs(Math.hypot(early.vx, early.vy) - MINE_SPEED_MIN) < 1e-9);
  const late = spawnMine(seq(0.5, 0.5, 0, 0), BOUNDS, GAME_DURATION_MS);
  assert.ok(Math.abs(Math.hypot(late.vx, late.vy) - MINE_SPEED_MAX) < 1e-9);
});

test('spawnMine: an unsafe roll is retried deterministically', () => {
  const player = { x: 100, y: 620 };
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  // First roll (0.2, 0.85) lands ~54px from the player; the retry (0.3, 0.1)
  // is far away and must be used verbatim.
  const mine = spawnMine(seq(0.2, 0.85, 0.3, 0.1, 0.5, 0.5), BOUNDS, 0, player);
  assert.equal(mine.x, margin + 0.3 * (BOUNDS.width - margin * 2));
  assert.equal(mine.y, margin + 0.1 * (BOUNDS.height - margin * 2));
  const dist = Math.hypot(mine.x - player.x, mine.y - player.y);
  assert.ok(dist >= MINE_SAFE_DISTANCE);
  // A roll already far from the player is kept as-is.
  const far = spawnMine(seq(0.9, 0.05, 0.3, 0.1), BOUNDS, 0, player);
  assert.equal(far.x, margin + 0.9 * (BOUNDS.width - margin * 2));
});

test('spawnMine: adversarial rand aiming every roll at the player still spawns safely', () => {
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  for (const player of playerGrid(BOUNDS)) {
    const mine = spawnMine(adversarialRand(player, BOUNDS, margin), BOUNDS, 0, player);
    const dist = Math.hypot(mine.x - player.x, mine.y - player.y);
    assert.ok(
      dist >= MINE_SAFE_DISTANCE,
      `player (${player.x},${player.y}) -> mine ${dist.toFixed(1)}px away (< ${MINE_SAFE_DISTANCE})`,
    );
    assert.ok(mine.x >= margin && mine.x <= BOUNDS.width - margin, 'x within spawn margins');
    assert.ok(mine.y >= margin && mine.y <= BOUNDS.height - margin, 'y within spawn margins');
  }
});

test('spawnMine: property sweep across RNG seeds and player positions', () => {
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  for (let seed = 1; seed <= 40; seed += 1) {
    const rand = lcg(seed);
    for (const player of playerGrid(BOUNDS)) {
      const mine = spawnMine(rand, BOUNDS, 30000, player);
      const dist = Math.hypot(mine.x - player.x, mine.y - player.y);
      assert.ok(
        dist >= MINE_SAFE_DISTANCE,
        `seed ${seed}, player (${player.x},${player.y}) -> ${dist.toFixed(1)}px`,
      );
      assert.ok(mine.x >= margin && mine.x <= BOUNDS.width - margin);
      assert.ok(mine.y >= margin && mine.y <= BOUNDS.height - margin);
    }
  }
});

test('spawnMine: player dead-center exhausts retries and takes a farthest corner', () => {
  const player = { x: BOUNDS.width / 2, y: BOUNDS.height / 2 };
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  // rand() === 0.5 lands every candidate exactly on the player, so the old
  // mirror-across-center fallback would also land on the player.
  const mine = spawnMine(() => 0.5, BOUNDS, 0, player);
  const maxX = BOUNDS.width - margin;
  const maxY = BOUNDS.height - margin;
  assert.ok(mine.x === margin || mine.x === maxX, 'fallback x is a spawn-rect corner');
  assert.ok(mine.y === margin || mine.y === maxY, 'fallback y is a spawn-rect corner');
  const dist = Math.hypot(mine.x - player.x, mine.y - player.y);
  assert.ok(dist >= MINE_SAFE_DISTANCE);
  // The corner fallback is the global optimum for the spawn rectangle.
  assert.ok(Math.abs(dist - farthestPossible(player, BOUNDS, margin)) < 1e-9);
});

test('spawnMine: arena too small for the guarantee degrades to the farthest point', () => {
  const tiny = { width: 150, height: 150 };
  const margin = SPAWN_MARGIN + MINE_RADIUS;
  const player = { x: 75, y: 75 };
  const mine = spawnMine(() => 0.5, tiny, 0, player);
  const dist = Math.hypot(mine.x - player.x, mine.y - player.y);
  const best = farthestPossible(player, tiny, margin);
  assert.ok(best < MINE_SAFE_DISTANCE, 'sanity: no valid point exists on this arena');
  assert.ok(Math.abs(dist - best) < 1e-9, 'fallback is the best position that exists');
  // Degenerate arena (spawn rect collapses to a point) must stay finite.
  const degenerate = spawnMine(() => 0.5, { width: 60, height: 60 }, 0, { x: margin, y: margin });
  assert.ok(Number.isFinite(degenerate.x) && Number.isFinite(degenerate.y));
});

test('spawnShard: avoidance guarantees a safe pickup distance', () => {
  const margin = SPAWN_MARGIN + SHARD_RADIUS;
  for (const player of playerGrid(BOUNDS)) {
    const shard = spawnShard(adversarialRand(player, BOUNDS, margin), BOUNDS, player);
    const dist = Math.hypot(shard.x - player.x, shard.y - player.y);
    assert.ok(
      dist >= SHARD_SAFE_DISTANCE,
      `player (${player.x},${player.y}) -> shard ${dist.toFixed(1)}px away (< ${SHARD_SAFE_DISTANCE})`,
    );
    assert.ok(dist > PLAYER_RADIUS + SHARD_RADIUS, 'never spawns pre-collected');
    assert.ok(shard.x >= margin && shard.x <= BOUNDS.width - margin);
    assert.ok(shard.y >= margin && shard.y <= BOUNDS.height - margin);
  }
});

test('spawnShard: property sweep across RNG seeds and player positions', () => {
  const margin = SPAWN_MARGIN + SHARD_RADIUS;
  for (let seed = 1; seed <= 40; seed += 1) {
    const rand = lcg(seed);
    for (const player of playerGrid(BOUNDS)) {
      const shard = spawnShard(rand, BOUNDS, player);
      const dist = Math.hypot(shard.x - player.x, shard.y - player.y);
      assert.ok(
        dist >= SHARD_SAFE_DISTANCE,
        `seed ${seed}, player (${player.x},${player.y}) -> ${dist.toFixed(1)}px`,
      );
    }
  }
});

test('spawnShard: a safe roll is used verbatim and stays deterministic', () => {
  const player = { x: 100, y: 620 };
  const margin = SPAWN_MARGIN + SHARD_RADIUS;
  const a = spawnShard(seq(0.9, 0.05, 0.5), BOUNDS, player);
  assert.equal(a.x, margin + 0.9 * (BOUNDS.width - margin * 2));
  assert.equal(a.y, margin + 0.05 * (BOUNDS.height - margin * 2));
  const b = spawnShard(seq(0.9, 0.05, 0.5), BOUNDS, player);
  assert.deepEqual(a, b);
});

test('integration: a scripted 60-second run produces the exact expected score', () => {
  // Twelve shards, one per second: multiplier walks 1..10 then stays capped.
  let run = createRunState();
  let now = 0;
  for (let i = 0; i < 12; i += 1) {
    now += 1000;
    ({ run } = collectShard(run, now));
  }
  // 10+20+...+100 = 550, plus two capped pickups at 100 each.
  assert.equal(run.score, 750);
  assert.equal(run.combo, COMBO_CAP);

  // Two mine hits leave one heart; the run survives to the buzzer.
  ({ run } = hitMine({ ...run, elapsedMs: now }, now));
  now += INVULN_MS + 100;
  ({ run } = hitMine({ ...run, elapsedMs: now }, now));
  assert.equal(run.health, 1);
  assert.equal(isGameOver(run), false);

  run = { ...run, elapsedMs: GAME_DURATION_MS };
  assert.equal(isGameOver(run), true);
  assert.equal(run.score, 750);
});
