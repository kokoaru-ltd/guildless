// Type declarations for gameRules.js (pure CommonJS module shared with the
// Node test runner). Keep in sync with the runtime exports.

export interface Vec2 {
  x: number;
  y: number;
}

export interface Bounds {
  width: number;
  height: number;
}

export interface RunState {
  elapsedMs: number;
  score: number;
  combo: number;
  comboExpiresAtMs: number;
  health: number;
  invulnerableUntilMs: number;
}

export interface ShardBody {
  x: number;
  y: number;
  r: number;
  phase: number;
}

export interface MineBody {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  phase: number;
}

export type Rand = () => number;

export const GAME_DURATION_MS: number;
export const MAX_HEALTH: number;
export const COMBO_CAP: number;
export const COMBO_WINDOW_MS: number;
export const INVULN_MS: number;
export const SHARD_BASE_SCORE: number;
export const DT_CLAMP_MS: number;
export const MINE_BASE_COUNT: number;
export const MINE_MAX_COUNT: number;
export const MINE_RAMP_INTERVAL_MS: number;
export const MINE_SPEED_MIN: number;
export const MINE_SPEED_MAX: number;
export const MINE_SAFE_DISTANCE: number;
export const SHARD_SAFE_DISTANCE: number;
export const SPAWN_ATTEMPTS: number;
export const PLAYER_RADIUS: number;
export const SHARD_RADIUS: number;
export const MINE_RADIUS: number;
export const SHARD_TARGET_COUNT: number;
export const SPAWN_MARGIN: number;
export const PLAYER_FOLLOW_RATE: number;

export function clampDelta(dtMs: number): number;
export function clampElapsedDelta(dtMs: number): number;
export function timeLeftMs(elapsedMs: number): number;
export function secondsLeft(elapsedMs: number): number;
export function isTimeUp(elapsedMs: number): boolean;
export function createRunState(): RunState;
export function isComboActive(run: RunState, nowMs: number): boolean;
export function comboWindowFraction(run: RunState, nowMs: number): number;
export function collectShard(run: RunState, nowMs: number): { run: RunState; gained: number };
export function isInvulnerable(run: RunState, nowMs: number): boolean;
export function hitMine(run: RunState, nowMs: number): { run: RunState; tookDamage: boolean };
export function isGameOver(run: RunState): boolean;
export function mineCountForElapsed(elapsedMs: number): number;
export function mineSpeedForElapsed(elapsedMs: number): number;
export function circlesOverlap(
  ax: number,
  ay: number,
  ar: number,
  bx: number,
  by: number,
  br: number,
): boolean;
export function clampToBounds(x: number, y: number, r: number, bounds: Bounds): Vec2;
export function stepPlayer(pos: Vec2, target: Vec2, dtMs: number): Vec2;
export function stepMine<T extends MineBody>(mine: T, dtMs: number, bounds: Bounds): T;
export function spawnShard(rand: Rand, bounds: Bounds, avoid?: Vec2): ShardBody;
export function spawnMine(rand: Rand, bounds: Bounds, elapsedMs: number, avoid?: Vec2): MineBody;
