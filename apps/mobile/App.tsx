import { StatusBar } from 'expo-status-bar';
import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AppState,
  GestureResponderEvent,
  LayoutChangeEvent,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import type { Bounds, MineBody, RunState, ShardBody, Vec2 } from './gameRules';
import {
  GAME_DURATION_MS,
  MAX_HEALTH,
  MINE_RADIUS,
  PLAYER_RADIUS,
  SHARD_RADIUS,
  SHARD_TARGET_COUNT,
  clampDelta,
  clampElapsedDelta,
  clampToBounds,
  circlesOverlap,
  collectShard,
  comboWindowFraction,
  createRunState,
  hitMine,
  isComboActive,
  isGameOver,
  isInvulnerable,
  mineCountForElapsed,
  secondsLeft,
  spawnMine,
  spawnShard,
  stepMine,
  stepPlayer,
  timeLeftMs,
} from './gameRules';

// The orb rides slightly above the fingertip so the thumb never hides it.
const THUMB_OFFSET = 48;

type Phase = 'menu' | 'playing' | 'paused' | 'over';

type World = {
  run: RunState;
  player: Vec2;
  target: Vec2;
  mines: Array<MineBody & { id: number }>;
  shards: Array<ShardBody & { id: number }>;
  nextId: number;
  touching: boolean;
  endReason: 'time' | 'down' | null;
  newBest: boolean;
};

function buzz(trigger: () => Promise<unknown>) {
  // Haptics are best-effort; never let an unsupported platform crash the loop.
  try {
    trigger().catch(() => {});
  } catch {
    // no-op
  }
}

export default function App() {
  const [phase, setPhase] = useState<Phase>('menu');
  const [, setFrame] = useState(0);

  const phaseRef = useRef<Phase>('menu');
  const worldRef = useRef<World | null>(null);
  const boundsRef = useRef<Bounds>({ width: 0, height: 0 });
  const bestRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);

  const startRun = useCallback(() => {
    const bounds = boundsRef.current;
    if (bounds.width <= 0 || bounds.height <= 0) return;
    const player = { x: bounds.width / 2, y: bounds.height * 0.7 };
    const world: World = {
      run: createRunState(),
      player,
      target: { ...player },
      mines: [],
      shards: [],
      nextId: 1,
      touching: false,
      endReason: null,
      newBest: false,
    };
    for (let i = 0; i < mineCountForElapsed(0); i += 1) {
      world.mines.push({ ...spawnMine(Math.random, bounds, 0, player), id: world.nextId++ });
    }
    for (let i = 0; i < SHARD_TARGET_COUNT; i += 1) {
      world.shards.push({ ...spawnShard(Math.random, bounds, player), id: world.nextId++ });
    }
    worldRef.current = world;
    buzz(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
    setPhase('playing');
  }, []);

  // The gameplay clock (timer, combo/invuln windows, difficulty ramp) advances
  // by wall-clock time; physics motion advances by the clamped delta so slow
  // frames never tunnel bodies through walls.
  const stepWorld = useCallback((physicsDtMs: number, elapsedDtMs: number) => {
    const world = worldRef.current;
    if (!world || world.endReason) return;
    const bounds = boundsRef.current;

    let run: RunState = { ...world.run, elapsedMs: world.run.elapsedMs + elapsedDtMs };
    const now = run.elapsedMs;

    world.player = stepPlayer(world.player, world.target, physicsDtMs);
    world.mines = world.mines.map((mine) => stepMine(mine, physicsDtMs, bounds));

    const wantMines = mineCountForElapsed(now);
    while (world.mines.length < wantMines) {
      world.mines.push({
        ...spawnMine(Math.random, bounds, now, world.player),
        id: world.nextId++,
      });
    }

    const kept: World['shards'] = [];
    for (const shard of world.shards) {
      if (circlesOverlap(world.player.x, world.player.y, PLAYER_RADIUS, shard.x, shard.y, shard.r)) {
        ({ run } = collectShard(run, now));
        buzz(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
      } else {
        kept.push(shard);
      }
    }
    world.shards = kept;
    while (world.shards.length < SHARD_TARGET_COUNT) {
      world.shards.push({ ...spawnShard(Math.random, bounds, world.player), id: world.nextId++ });
    }

    if (!isInvulnerable(run, now)) {
      for (const mine of world.mines) {
        if (circlesOverlap(world.player.x, world.player.y, PLAYER_RADIUS, mine.x, mine.y, mine.r)) {
          const hit = hitMine(run, now);
          run = hit.run;
          if (hit.tookDamage) {
            buzz(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
          }
          break;
        }
      }
    }

    world.run = run;

    if (isGameOver(run)) {
      world.endReason = run.health <= 0 ? 'down' : 'time';
      world.newBest = run.score > bestRef.current && run.score > 0;
      bestRef.current = Math.max(bestRef.current, run.score);
      buzz(() =>
        world.newBest
          ? Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)
          : Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
      );
      setPhase('over');
    }
  }, []);

  const frame = useCallback(
    (ts: number) => {
      // lastTsRef is reset to null whenever the loop (re)starts, so the first
      // frame after start or resume contributes zero time — no resume spikes.
      const rawDt = lastTsRef.current == null ? 0 : ts - lastTsRef.current;
      lastTsRef.current = ts;
      stepWorld(clampDelta(rawDt), clampElapsedDelta(rawDt));
      setFrame((f) => f + 1);
      if (phaseRef.current === 'playing') {
        rafRef.current = requestAnimationFrame(frame);
      }
    },
    [stepWorld],
  );

  useEffect(() => {
    phaseRef.current = phase;
    if (phase !== 'playing') return undefined;
    lastTsRef.current = null;
    rafRef.current = requestAnimationFrame(frame);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [phase, frame]);

  // Backgrounding the app must never cost the player a run.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active' && phaseRef.current === 'playing') {
        setPhase('paused');
      }
    });
    return () => sub.remove();
  }, []);

  const onArenaLayout = useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    boundsRef.current = { width, height };
  }, []);

  const onTouch = useCallback((event: GestureResponderEvent) => {
    const world = worldRef.current;
    if (!world) return;
    const { locationX, locationY } = event.nativeEvent;
    world.touching = true;
    world.target = clampToBounds(locationX, locationY - THUMB_OFFSET, PLAYER_RADIUS, boundsRef.current);
  }, []);

  const onTouchEnd = useCallback(() => {
    const world = worldRef.current;
    if (world) world.touching = false;
  }, []);

  const pauseRun = useCallback(() => {
    buzz(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
    setPhase('paused');
  }, []);

  const resumeRun = useCallback(() => {
    buzz(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
    setPhase('playing');
  }, []);

  const quitToMenu = useCallback(() => {
    worldRef.current = null;
    setPhase('menu');
  }, []);

  const world = worldRef.current;
  const run = world?.run ?? null;
  const now = run?.elapsedMs ?? 0;
  const seconds = run ? secondsLeft(now) : 60;
  const urgent = phase === 'playing' && seconds <= 10;
  const comboOn = run != null && isComboActive(run, now) && run.combo > 1;
  const invulnerable = run != null && isInvulnerable(run, now);
  const playerVisible = !invulnerable || Math.floor(now / 100) % 2 === 0;
  const timeFraction = run ? timeLeftMs(now) / GAME_DURATION_MS : 1;

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <LinearGradient colors={['#0A1024', '#05070F', '#04050B']} style={StyleSheet.absoluteFill} />
      <View style={styles.glowTop} pointerEvents="none" />
      <View style={styles.glowBottom} pointerEvents="none" />

      <SafeAreaView style={styles.safe}>
        <View style={styles.hud}>
          <View style={styles.hudRow}>
            <View style={styles.hudLeft}>
              <View style={styles.heartsRow}>
                {Array.from({ length: MAX_HEALTH }, (_, i) => (
                  <Text
                    key={i}
                    style={[styles.heart, run != null && i >= run.health && styles.heartLost]}
                  >
                    {'♥'}
                  </Text>
                ))}
              </View>
              <View style={[styles.comboChip, !comboOn && styles.comboChipIdle]}>
                <Text style={styles.comboText}>{comboOn && run ? `×${run.combo}` : '×1'}</Text>
                <View style={styles.comboTrack}>
                  <View
                    style={[
                      styles.comboFill,
                      { width: run ? `${comboWindowFraction(run, now) * 100}%` : '0%' },
                    ]}
                  />
                </View>
              </View>
            </View>

            <Text style={[styles.timer, urgent && styles.timerUrgent]}>{seconds}</Text>

            <View style={styles.hudRight}>
              <Text style={styles.scoreLabel}>SCORE</Text>
              <Text style={styles.scoreValue}>{run ? run.score : 0}</Text>
              {phase === 'playing' ? (
                <Pressable
                  accessibilityLabel="Pause"
                  accessibilityRole="button"
                  hitSlop={8}
                  onPress={pauseRun}
                  style={({ pressed }) => [styles.pauseButton, pressed && styles.pressed]}
                >
                  <View style={styles.pauseBar} />
                  <View style={styles.pauseBar} />
                </Pressable>
              ) : (
                <View style={styles.pauseSpacer} />
              )}
            </View>
          </View>
          <View style={styles.timeTrack}>
            <View
              style={[
                styles.timeFill,
                { width: `${timeFraction * 100}%` },
                urgent && styles.timeFillUrgent,
              ]}
            />
          </View>
        </View>

        <View
          style={styles.arena}
          onLayout={onArenaLayout}
          onStartShouldSetResponder={() => true}
          onMoveShouldSetResponder={() => true}
          onResponderGrant={onTouch}
          onResponderMove={onTouch}
          onResponderRelease={onTouchEnd}
          onResponderTerminate={onTouchEnd}
        >
          {world && (
            <View style={StyleSheet.absoluteFill} pointerEvents="none">
              {world.shards.map((shard) => {
                const scale = 0.93 + 0.07 * Math.sin(shard.phase + now * 0.005);
                return (
                  <View
                    key={shard.id}
                    style={[
                      styles.shard,
                      {
                        transform: [
                          { translateX: shard.x - SHARD_VISUAL / 2 },
                          { translateY: shard.y - SHARD_VISUAL / 2 },
                          { rotate: '45deg' },
                          { scale },
                        ],
                      },
                    ]}
                  />
                );
              })}
              {world.mines.map((mine) => {
                const scale = 0.95 + 0.05 * Math.sin(mine.phase);
                return (
                  <View
                    key={mine.id}
                    style={[
                      styles.mine,
                      {
                        transform: [
                          { translateX: mine.x - MINE_VISUAL / 2 },
                          { translateY: mine.y - MINE_VISUAL / 2 },
                          { scale },
                        ],
                      },
                    ]}
                  >
                    <View style={styles.mineCore} />
                  </View>
                );
              })}
              {world.touching && phase === 'playing' && (
                <View
                  style={[
                    styles.targetRing,
                    {
                      transform: [
                        { translateX: world.target.x - TARGET_RING / 2 },
                        { translateY: world.target.y - TARGET_RING / 2 },
                      ],
                    },
                  ]}
                />
              )}
              <View
                style={[
                  styles.player,
                  !playerVisible && styles.playerBlink,
                  {
                    transform: [
                      { translateX: world.player.x - PLAYER_VISUAL / 2 },
                      { translateY: world.player.y - PLAYER_VISUAL / 2 },
                    ],
                  },
                ]}
              >
                <View style={styles.playerCore} />
              </View>
            </View>
          )}
        </View>
      </SafeAreaView>

      {phase === 'menu' && (
        <View style={styles.overlay}>
          <LinearGradient colors={['#0A1024', '#05070F']} style={StyleSheet.absoluteFill} />
          <View style={styles.glowTop} pointerEvents="none" />
          <SafeAreaView style={styles.overlaySafe}>
            <View style={styles.menuBody}>
              <Text style={styles.kicker}>60 SECONDS {'·'} ONE THUMB</Text>
              <Text style={styles.titleNeon}>NEON</Text>
              <Text style={styles.titleDrift}>DRIFT</Text>

              <View style={styles.rules}>
                <View style={styles.ruleRow}>
                  <View style={styles.ruleIconOrb} />
                  <Text style={styles.ruleText}>Drag the arena below the scoreboard. Your orb chases your thumb.</Text>
                </View>
                <View style={styles.ruleRow}>
                  <View style={styles.ruleIconShard} />
                  <Text style={styles.ruleText}>Catch shards. Chain them within 2.5s for up to a {'×'}10 combo.</Text>
                </View>
                <View style={styles.ruleRow}>
                  <View style={styles.ruleIconMine} />
                  <Text style={styles.ruleText}>Dodge mines. Each hit costs a heart. Three hearts per run.</Text>
                </View>
              </View>

              {bestRef.current > 0 && (
                <Text style={styles.bestLine}>SESSION BEST {bestRef.current}</Text>
              )}
            </View>
            <View style={styles.overlayFooter}>
              <Pressable
                accessibilityRole="button"
                onPress={startRun}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.primaryButtonText}>PLAY</Text>
              </Pressable>
            </View>
          </SafeAreaView>
        </View>
      )}

      {phase === 'paused' && (
        <View style={[styles.overlay, styles.dimOverlay]}>
          <SafeAreaView style={styles.overlaySafe}>
            <View style={styles.menuBody}>
              <Text style={styles.kicker}>RUN FROZEN</Text>
              <Text style={styles.overlayTitle}>PAUSED</Text>
              <Text style={styles.overlayHint}>
                {run ? `${secondsLeft(now)}s left · ${run.score} pts` : ''}
              </Text>
            </View>
            <View style={styles.overlayFooter}>
              <Pressable
                accessibilityRole="button"
                onPress={resumeRun}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.primaryButtonText}>RESUME</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={quitToMenu}
                style={({ pressed }) => [styles.ghostButton, pressed && styles.pressed]}
              >
                <Text style={styles.ghostButtonText}>QUIT RUN</Text>
              </Pressable>
            </View>
          </SafeAreaView>
        </View>
      )}

      {phase === 'over' && world && run && (
        <View style={[styles.overlay, styles.dimOverlay]}>
          <SafeAreaView style={styles.overlaySafe}>
            <View style={styles.menuBody}>
              <Text style={[styles.kicker, world.endReason === 'down' && styles.kickerDanger]}>
                {world.endReason === 'down' ? 'CORE DESTROYED' : 'RUN COMPLETE'}
              </Text>
              <Text style={styles.finalScore}>{run.score}</Text>
              <Text style={styles.overlayHint}>
                {world.newBest ? 'NEW SESSION BEST' : `SESSION BEST ${bestRef.current}`}
              </Text>
            </View>
            <View style={styles.overlayFooter}>
              <Pressable
                accessibilityRole="button"
                onPress={startRun}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.primaryButtonText}>RETRY</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={quitToMenu}
                style={({ pressed }) => [styles.ghostButton, pressed && styles.pressed]}
              >
                <Text style={styles.ghostButtonText}>MENU</Text>
              </Pressable>
            </View>
          </SafeAreaView>
        </View>
      )}
    </View>
  );
}

// Visual footprints match the collision diameters exactly.
const PLAYER_VISUAL = PLAYER_RADIUS * 2;
// The rotated square's diagonal remains inside the circular hit radius.
const SHARD_VISUAL = SHARD_RADIUS * Math.SQRT2;
const MINE_VISUAL = MINE_RADIUS * 2;
const TARGET_RING = 30;

const CYAN = '#53F1FF';
const LIME = '#D8FF62';
const MAGENTA = '#FF4D6E';
const INK = '#EAF2FF';
const DIM = '#8A93A8';

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#04050B' },
  safe: { flex: 1 },
  glowTop: {
    position: 'absolute',
    width: 420,
    height: 420,
    borderRadius: 210,
    backgroundColor: 'rgba(83,241,255,0.07)',
    top: -240,
    left: -120,
  },
  glowBottom: {
    position: 'absolute',
    width: 380,
    height: 380,
    borderRadius: 190,
    backgroundColor: 'rgba(255,77,110,0.055)',
    bottom: -220,
    right: -140,
  },

  hud: {
    paddingHorizontal: 20,
    paddingTop: Platform.OS === 'android' ? 24 : 6,
  },
  hudRow: {
    height: 92,
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  hudLeft: { width: 108, paddingTop: 8 },
  heartsRow: { flexDirection: 'row', gap: 4 },
  heart: {
    color: MAGENTA,
    fontSize: 20,
    textShadowColor: 'rgba(255,77,110,0.75)',
    textShadowRadius: 10,
  },
  heartLost: { color: '#232A3D', textShadowColor: 'transparent' },
  comboChip: { marginTop: 10, width: 88 },
  comboChipIdle: { opacity: 0.35 },
  comboText: {
    color: LIME,
    fontSize: 20,
    fontWeight: '900',
    fontVariant: ['tabular-nums'],
    textShadowColor: 'rgba(216,255,98,0.6)',
    textShadowRadius: 8,
  },
  comboTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: '#1A2233',
    marginTop: 5,
    overflow: 'hidden',
  },
  comboFill: { height: 4, borderRadius: 2, backgroundColor: LIME },
  timer: {
    color: INK,
    fontSize: 58,
    fontWeight: '800',
    letterSpacing: -2,
    fontVariant: ['tabular-nums'],
    textShadowColor: 'rgba(83,241,255,0.35)',
    textShadowRadius: 16,
  },
  timerUrgent: { color: MAGENTA, textShadowColor: 'rgba(255,77,110,0.55)' },
  hudRight: { width: 108, alignItems: 'flex-end', paddingTop: 8 },
  scoreLabel: { color: DIM, fontSize: 10, fontWeight: '800', letterSpacing: 1.6 },
  scoreValue: {
    color: INK,
    fontSize: 26,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
    marginTop: 2,
  },
  pauseButton: {
    width: 48,
    height: 48,
    borderRadius: 14,
    marginTop: 2,
    backgroundColor: 'rgba(20,27,45,0.85)',
    borderWidth: 1,
    borderColor: '#26314C',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
  },
  pauseSpacer: { width: 48, height: 48, marginTop: 2 },
  pauseBar: { width: 5, height: 18, borderRadius: 2.5, backgroundColor: INK },
  timeTrack: {
    height: 3,
    borderRadius: 1.5,
    backgroundColor: '#131A2C',
    overflow: 'hidden',
    marginTop: 2,
  },
  timeFill: { height: 3, borderRadius: 1.5, backgroundColor: CYAN },
  timeFillUrgent: { backgroundColor: MAGENTA },

  arena: { flex: 1 },
  player: {
    position: 'absolute',
    width: PLAYER_VISUAL,
    height: PLAYER_VISUAL,
    borderRadius: PLAYER_VISUAL / 2,
    backgroundColor: 'rgba(83,241,255,0.22)',
    borderWidth: 2,
    borderColor: CYAN,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: CYAN,
    shadowOpacity: 0.9,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 10,
  },
  playerBlink: { opacity: 0.3 },
  playerCore: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#DFFCFF',
  },
  shard: {
    position: 'absolute',
    width: SHARD_VISUAL,
    height: SHARD_VISUAL,
    borderRadius: 4,
    backgroundColor: LIME,
    shadowColor: LIME,
    shadowOpacity: 0.9,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 0 },
    elevation: 8,
  },
  mine: {
    position: 'absolute',
    width: MINE_VISUAL,
    height: MINE_VISUAL,
    borderRadius: MINE_VISUAL / 2,
    backgroundColor: 'rgba(255,77,110,0.12)',
    borderWidth: 2,
    borderColor: MAGENTA,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: MAGENTA,
    shadowOpacity: 0.8,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 0 },
    elevation: 8,
  },
  mineCore: { width: 8, height: 8, borderRadius: 4, backgroundColor: MAGENTA },
  targetRing: {
    position: 'absolute',
    width: TARGET_RING,
    height: TARGET_RING,
    borderRadius: TARGET_RING / 2,
    borderWidth: 1.5,
    borderColor: 'rgba(234,242,255,0.28)',
  },

  overlay: { ...StyleSheet.absoluteFillObject },
  dimOverlay: { backgroundColor: 'rgba(4,6,12,0.9)' },
  overlaySafe: { flex: 1, paddingHorizontal: 28 },
  menuBody: { flex: 1, justifyContent: 'center' },
  kicker: {
    color: CYAN,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 3,
    marginBottom: 14,
  },
  kickerDanger: { color: MAGENTA },
  titleNeon: {
    color: CYAN,
    fontSize: 64,
    fontWeight: '900',
    letterSpacing: 8,
    lineHeight: 68,
    textShadowColor: 'rgba(83,241,255,0.6)',
    textShadowRadius: 22,
  },
  titleDrift: {
    color: INK,
    fontSize: 64,
    fontWeight: '900',
    letterSpacing: 8,
    lineHeight: 72,
  },
  rules: { marginTop: 36, gap: 18 },
  ruleRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  ruleIconOrb: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: CYAN,
    backgroundColor: 'rgba(83,241,255,0.2)',
  },
  ruleIconShard: {
    width: 16,
    height: 16,
    borderRadius: 3,
    backgroundColor: LIME,
    transform: [{ rotate: '45deg' }],
  },
  ruleIconMine: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: MAGENTA,
    backgroundColor: 'rgba(255,77,110,0.15)',
  },
  ruleText: { color: DIM, fontSize: 15, lineHeight: 21, flex: 1 },
  bestLine: {
    color: LIME,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 2,
    marginTop: 30,
    fontVariant: ['tabular-nums'],
  },
  overlayTitle: {
    color: INK,
    fontSize: 52,
    fontWeight: '900',
    letterSpacing: 4,
  },
  overlayHint: {
    color: DIM,
    fontSize: 15,
    marginTop: 16,
    fontVariant: ['tabular-nums'],
    letterSpacing: 1,
  },
  finalScore: {
    color: INK,
    fontSize: 96,
    fontWeight: '900',
    letterSpacing: -2,
    fontVariant: ['tabular-nums'],
    textShadowColor: 'rgba(83,241,255,0.4)',
    textShadowRadius: 24,
  },
  overlayFooter: { paddingBottom: Platform.OS === 'ios' ? 18 : 28, gap: 12 },
  primaryButton: {
    height: 60,
    borderRadius: 18,
    backgroundColor: CYAN,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: CYAN,
    shadowOpacity: 0.45,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
    elevation: 10,
  },
  primaryButtonText: {
    color: '#04121A',
    fontSize: 17,
    fontWeight: '900',
    letterSpacing: 3,
  },
  ghostButton: {
    height: 56,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#2A3450',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(13,18,33,0.6)',
  },
  ghostButtonText: { color: DIM, fontSize: 14, fontWeight: '800', letterSpacing: 2.5 },
  pressed: { opacity: 0.75, transform: [{ scale: 0.98 }] },
});
