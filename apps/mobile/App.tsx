import { StatusBar } from 'expo-status-bar';
import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';
import { useState } from 'react';
import {
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

type Brief = { goal: string; deadline: string; budget: string };

const suggestedGoals = [
  'Ship an iOS game',
  'Launch a SaaS',
  'Build a marketplace',
];

const crew = [
  ['ARCHITECT', 'Codex', 'Scope, system design, acceptance tests', '#A9C7FF'],
  ['BUILDER', 'Claude', 'Production implementation', '#E9A879'],
  ['VERIFIER', 'Gemini', 'Independent review and visual QA', '#82D9B1'],
  ['OPERATOR', 'Kimi', 'Monitoring, triage, maintenance', '#B6A4FF'],
];

export default function App() {
  const [goal, setGoal] = useState('');
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [brief, setBrief] = useState<Brief>({ goal: '', deadline: '30 days', budget: '$500' });

  const next = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (step === 1 && goal.trim()) {
      setBrief((current) => ({ ...current, goal: goal.trim() }));
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    }
  };

  if (step === 3) return <CommandCenter brief={brief} onReset={() => setStep(1)} />;

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <LinearGradient colors={['#111419', '#090A0D']} style={StyleSheet.absoluteFill} />
      <View style={styles.glow} />
      <SafeAreaView style={styles.safe}>
        <View style={styles.nav}>
          <Text style={styles.wordmark}>GUILDLESS</Text>
          <Text style={styles.stepLabel}>0{step} / 02</Text>
        </View>

        <View style={styles.onboarding}>
          <View style={styles.eyebrowRow}>
            <View style={styles.signal} />
            <Text style={styles.eyebrow}>{step === 1 ? 'YOUR FIRST MISSION' : 'OPERATING LIMITS'}</Text>
          </View>

          {step === 1 ? (
            <>
              <Text style={styles.hero}>What should your{`\n`}company ship?</Text>
              <Text style={styles.heroBody}>
                Give us the outcome. Your AI company will plan the work, assign specialists, verify every handoff, and ask only when judgment matters.
              </Text>
              <View style={styles.inputShell}>
                <TextInput
                  autoFocus
                  accessibilityLabel="Mission outcome"
                  multiline
                  placeholder="e.g. Ship a multiplayer roguelite on Steam"
                  placeholderTextColor="#666B74"
                  selectionColor="#D8FF62"
                  value={goal}
                  onChangeText={setGoal}
                  style={styles.input}
                />
                <Text style={styles.inputHint}>OUTCOME, NOT TASKS</Text>
              </View>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
                {suggestedGoals.map((item) => (
                  <Pressable key={item} onPress={() => setGoal(item)} style={({ pressed }) => [styles.chip, pressed && styles.pressed]}>
                    <Text style={styles.chipText}>{item}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            </>
          ) : (
            <>
              <Text style={styles.hero}>Set the boundaries.{`\n`}We handle the work.</Text>
              <Text style={styles.heroBody}>These are guardrails, not a project plan. You can change them while the mission is running.</Text>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>MISSION</Text>
                <Text style={styles.summaryValue}>{brief.goal}</Text>
              </View>
              <Choice label="TARGET" value={brief.deadline} options={['14 days', '30 days', '90 days']} onChange={(deadline) => setBrief({ ...brief, deadline })} />
              <Choice label="MAX SPEND" value={brief.budget} options={['$100', '$500', '$2,000']} onChange={(budget) => setBrief({ ...brief, budget })} />
              <View style={styles.guardrail}>
                <Text style={styles.guardrailMark}>✓</Text>
                <Text style={styles.guardrailText}>Purchases, publishing, and destructive actions always require your approval.</Text>
              </View>
            </>
          )}
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerNote}>{step === 1 ? 'No setup. No org chart.' : 'You remain the final authority.'}</Text>
          <Pressable disabled={step === 1 && !goal.trim()} onPress={next} style={({ pressed }) => [styles.continueButton, step === 1 && !goal.trim() && styles.buttonDisabled, pressed && styles.pressed]}>
            <Text style={styles.continueText}>{step === 1 ? 'Continue' : 'Launch company'}</Text>
            <Text style={styles.arrow}>→</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

function Choice({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <View style={styles.choiceBlock}>
      <Text style={styles.choiceLabel}>{label}</Text>
      <View style={styles.choiceRow}>
        {options.map((option) => (
          <Pressable key={option} onPress={() => onChange(option)} style={({ pressed }) => [styles.choice, value === option && styles.choiceActive, pressed && styles.pressed]}>
            <Text style={[styles.choiceText, value === option && styles.choiceTextActive]}>{option}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function CommandCenter({ brief, onReset }: { brief: Brief; onReset: () => void }) {
  const [approved, setApproved] = useState(false);
  const approve = async () => {
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setApproved(true);
  };

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <LinearGradient colors={['#111419', '#090A0D']} style={StyleSheet.absoluteFill} />
      <SafeAreaView style={styles.safe}>
        <View style={styles.nav}>
          <Text style={styles.wordmark}>GUILDLESS</Text>
          <Pressable onPress={onReset} style={({ pressed }) => [styles.profile, pressed && styles.pressed]}><Text style={styles.profileText}>K</Text></Pressable>
        </View>
        <ScrollView contentContainerStyle={styles.commandScroll} showsVerticalScrollIndicator={false}>
          <View style={styles.liveRow}><View style={styles.signal} /><Text style={styles.eyebrow}>COMPANY ONLINE</Text><Text style={styles.elapsed}>00:01:42</Text></View>
          <Text style={styles.commandTitle}>{brief.goal}</Text>
          <Text style={styles.commandMeta}>{brief.deadline} · {brief.budget} ceiling</Text>

          <View style={styles.progressCard}>
            <View style={styles.progressTop}><Text style={styles.progressPhase}>DISCOVERY</Text><Text style={styles.progressPercent}>12%</Text></View>
            <View style={styles.track}><View style={styles.fill} /></View>
            <Text style={styles.progressDetail}>Codex is decomposing the mission into independently verifiable work.</Text>
          </View>

          <Text style={styles.sectionLabel}>AUTONOMOUS CREW</Text>
          <View style={styles.crewList}>
            {crew.map(([role, model, task, color], index) => (
              <View style={[styles.crewRow, index === crew.length - 1 && { borderBottomWidth: 0 }]} key={role}>
                <View style={[styles.crewMark, { backgroundColor: color }]}><Text style={styles.crewMarkText}>{model[0]}</Text></View>
                <View style={styles.crewCopy}><Text style={styles.crewRole}>{role}</Text><Text style={styles.crewTask}>{task}</Text></View>
                <View style={styles.modelBadge}><Text style={styles.modelText}>{model}</Text></View>
              </View>
            ))}
          </View>

          <Text style={styles.sectionLabel}>YOUR ATTENTION</Text>
          <View style={[styles.decision, approved && styles.decisionApproved]}>
            <Text style={styles.decisionLabel}>{approved ? 'DECISION RECORDED' : 'HIGH-IMPACT DECISION'}</Text>
            <Text style={styles.decisionTitle}>{approved ? 'The crew is moving forward.' : 'Approve the product direction'}</Text>
            <Text style={styles.decisionBody}>{approved ? 'Every downstream agent received the decision and its rationale.' : 'Three concepts were challenged by separate reviewers. Concept B has the strongest retention hypothesis and lowest delivery risk.'}</Text>
            {!approved && <Pressable onPress={approve} style={({ pressed }) => [styles.approve, pressed && styles.pressed]}><Text style={styles.approveText}>Review evidence</Text><Text style={styles.darkArrow}>→</Text></Pressable>}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#090A0D' },
  safe: { flex: 1 },
  glow: { position: 'absolute', width: 360, height: 360, borderRadius: 180, backgroundColor: 'rgba(157,190,91,.09)', top: -210, right: -100 },
  nav: { height: 72, paddingHorizontal: 22, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: Platform.OS === 'android' ? 18 : 0 },
  wordmark: { color: '#F4F5F2', fontSize: 14, fontWeight: '800', letterSpacing: 2.2 },
  stepLabel: { color: '#747982', fontSize: 11, fontWeight: '700', letterSpacing: 1.2, fontVariant: ['tabular-nums'] },
  onboarding: { flex: 1, paddingHorizontal: 22, paddingTop: 42 },
  eyebrowRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 18 },
  signal: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#D8FF62', marginRight: 8 },
  eyebrow: { color: '#AAB1B8', fontSize: 10, fontWeight: '800', letterSpacing: 1.6 },
  hero: { color: '#F4F5F2', fontSize: 39, lineHeight: 43, letterSpacing: -1.5, fontWeight: '700' },
  heroBody: { color: '#91969E', fontSize: 15, lineHeight: 23, marginTop: 18, maxWidth: 360 },
  inputShell: { minHeight: 132, borderRadius: 20, backgroundColor: '#15181D', borderWidth: 1, borderColor: '#343A43', marginTop: 34, padding: 18 },
  input: { flex: 1, color: '#F5F6F3', fontSize: 18, lineHeight: 25, textAlignVertical: 'top', padding: 0 },
  inputHint: { color: '#626871', fontSize: 8, fontWeight: '800', letterSpacing: 1.2, marginTop: 12 },
  chips: { gap: 8, paddingTop: 13, paddingRight: 22 },
  chip: { borderWidth: 1, borderColor: '#30353D', borderRadius: 99, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: '#111419' },
  chipText: { color: '#A8ADB5', fontSize: 11, fontWeight: '600' },
  footer: { paddingHorizontal: 22, paddingBottom: Platform.OS === 'ios' ? 10 : 18, flexDirection: 'row', alignItems: 'center', gap: 14 },
  footerNote: { flex: 1, color: '#626871', fontSize: 10 },
  continueButton: { minWidth: 166, height: 56, borderRadius: 17, paddingHorizontal: 19, backgroundColor: '#D8FF62', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  buttonDisabled: { opacity: .28 },
  continueText: { color: '#12150D', fontSize: 14, fontWeight: '800' },
  arrow: { color: '#12150D', fontSize: 21, marginLeft: 20 },
  pressed: { opacity: .72, transform: [{ scale: .975 }] },
  summaryCard: { backgroundColor: '#15181D', borderRadius: 18, borderWidth: 1, borderColor: '#2B3038', padding: 17, marginTop: 28 },
  summaryLabel: { color: '#656B74', fontSize: 8, fontWeight: '800', letterSpacing: 1.3 },
  summaryValue: { color: '#E9EBE7', fontSize: 15, lineHeight: 21, fontWeight: '600', marginTop: 8 },
  choiceBlock: { marginTop: 24 },
  choiceLabel: { color: '#777D86', fontSize: 9, fontWeight: '800', letterSpacing: 1.3, marginBottom: 10 },
  choiceRow: { flexDirection: 'row', gap: 8 },
  choice: { flex: 1, height: 45, borderRadius: 13, borderWidth: 1, borderColor: '#2D323A', alignItems: 'center', justifyContent: 'center', backgroundColor: '#12151A' },
  choiceActive: { backgroundColor: '#EAECE7', borderColor: '#EAECE7' },
  choiceText: { color: '#848A93', fontSize: 11, fontWeight: '700' },
  choiceTextActive: { color: '#171A16' },
  guardrail: { flexDirection: 'row', backgroundColor: '#131812', borderRadius: 14, padding: 14, marginTop: 24, alignItems: 'flex-start' },
  guardrailMark: { color: '#D8FF62', fontSize: 12, fontWeight: '900', marginRight: 10 },
  guardrailText: { color: '#8F9987', fontSize: 10, lineHeight: 15, flex: 1 },
  profile: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#20242A', alignItems: 'center', justifyContent: 'center' },
  profileText: { color: '#D8FF62', fontSize: 12, fontWeight: '800' },
  commandScroll: { paddingHorizontal: 22, paddingTop: 28, paddingBottom: 60 },
  liveRow: { flexDirection: 'row', alignItems: 'center' },
  elapsed: { color: '#616770', fontSize: 9, fontVariant: ['tabular-nums'], marginLeft: 'auto' },
  commandTitle: { color: '#F3F4F1', fontSize: 31, lineHeight: 36, letterSpacing: -1, fontWeight: '700', marginTop: 16 },
  commandMeta: { color: '#737982', fontSize: 11, marginTop: 9 },
  progressCard: { borderRadius: 20, backgroundColor: '#15191D', borderWidth: 1, borderColor: '#2A3037', padding: 18, marginTop: 28 },
  progressTop: { flexDirection: 'row', justifyContent: 'space-between' },
  progressPhase: { color: '#D8FF62', fontSize: 9, fontWeight: '800', letterSpacing: 1.3 },
  progressPercent: { color: '#8C929A', fontSize: 10, fontWeight: '700' },
  track: { height: 4, backgroundColor: '#2A2F34', borderRadius: 2, marginTop: 15, overflow: 'hidden' },
  fill: { width: '12%', height: 4, backgroundColor: '#D8FF62', borderRadius: 2 },
  progressDetail: { color: '#8D939B', fontSize: 11, lineHeight: 17, marginTop: 14 },
  sectionLabel: { color: '#676D76', fontSize: 9, fontWeight: '800', letterSpacing: 1.5, marginTop: 28, marginBottom: 11 },
  crewList: { backgroundColor: '#13161A', borderRadius: 20, paddingHorizontal: 15, borderWidth: 1, borderColor: '#292E35' },
  crewRow: { minHeight: 69, flexDirection: 'row', alignItems: 'center', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#292E35' },
  crewMark: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  crewMarkText: { color: '#14171A', fontSize: 11, fontWeight: '900' },
  crewCopy: { flex: 1 },
  crewRole: { color: '#E1E4E0', fontSize: 10, fontWeight: '800', letterSpacing: .7 },
  crewTask: { color: '#6F757E', fontSize: 9, marginTop: 4 },
  modelBadge: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: 7, backgroundColor: '#20242A' },
  modelText: { color: '#8D939C', fontSize: 8, fontWeight: '700' },
  decision: { backgroundColor: '#211B18', borderRadius: 20, borderWidth: 1, borderColor: '#49382F', padding: 18 },
  decisionApproved: { backgroundColor: '#151D15', borderColor: '#344832' },
  decisionLabel: { color: '#EFA06C', fontSize: 8, fontWeight: '800', letterSpacing: 1.3 },
  decisionTitle: { color: '#F2F1EE', fontSize: 17, fontWeight: '700', marginTop: 12 },
  decisionBody: { color: '#968D88', fontSize: 11, lineHeight: 17, marginTop: 8 },
  approve: { height: 48, borderRadius: 14, backgroundColor: '#F0F1ED', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, marginTop: 17 },
  approveText: { color: '#171914', fontSize: 12, fontWeight: '800' },
  darkArrow: { color: '#171914', fontSize: 18 },
});
