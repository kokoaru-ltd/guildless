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
  View,
} from 'react-native';

type Agent = {
  mark: string;
  name: string;
  provider: string;
  task: string;
  status: 'working' | 'waiting' | 'reviewing';
  color: string;
};

const agents: Agent[] = [
  { mark: 'C', name: 'Builder', provider: 'Claude', task: '戦闘システムを実装', status: 'working', color: '#E29B67' },
  { mark: 'O', name: 'Reviewer', provider: 'Codex', task: '差分とテストを検査', status: 'reviewing', color: '#59A8FF' },
  { mark: 'K', name: 'Operator', provider: 'Kimi', task: 'ログと障害を監視', status: 'working', color: '#8D7CFF' },
  { mark: 'G', name: 'Media', provider: 'Gemini', task: 'プレイ動画を解析', status: 'waiting', color: '#51C991' },
];

const stages = [
  ['仕様', '完了', true],
  ['非公開テスト', '完了', true],
  ['実装', '18 / 31', true],
  ['相互レビュー', '進行中', true],
  ['実機ビルド', '待機', false],
];

export default function App() {
  const [approved, setApproved] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const approve = async () => {
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setApproved(true);
  };

  return (
    <LinearGradient colors={['#10161A', '#080A0D']} style={styles.background}>
      <SafeAreaView style={styles.safe}>
        <StatusBar style="light" />
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={styles.header}>
            <View>
              <Text style={styles.brand}>GUILDLESS</Text>
              <Text style={styles.subtitle}>ONE PERSON · FULL STUDIO</Text>
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel="設定" style={({ pressed }) => [styles.avatar, pressed && styles.pressed]}>
              <Text style={styles.avatarText}>K</Text>
            </Pressable>
          </View>

          <LinearGradient colors={['#27351F', '#18231B']} style={styles.missionCard}>
            <View style={styles.missionTop}>
              <View style={styles.livePill}><View style={styles.liveDot} /><Text style={styles.liveText}>LIVE MISSION</Text></View>
              <Text style={styles.day}>DAY 18 / 90</Text>
            </View>
            <Text style={styles.missionTitle}>協力型ローグライトを{`\n`}Steamへ公開する</Text>
            <Text style={styles.missionMeta}>Nightfall · 予算 ¥100,000 / 月</Text>
            <View style={styles.progressTrack}><View style={[styles.progressFill, { width: '21%' }]} /></View>
            <View style={styles.metrics}>
              <View><Text style={styles.metricValue}>47</Text><Text style={styles.metricLabel}>今日のタスク</Text></View>
              <View><Text style={styles.metricValue}>12</Text><Text style={styles.metricLabel}>稼働中AI</Text></View>
              <View><Text style={styles.metricValue}>¥38k</Text><Text style={styles.metricLabel}>今月の費用</Text></View>
            </View>
          </LinearGradient>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>AI Studio</Text>
            <Text style={styles.sectionAction}>役割で自動選択</Text>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.agentRow}>
            {agents.map((agent) => (
              <Pressable
                key={agent.provider}
                accessibilityRole="button"
                accessibilityLabel={`${agent.provider}、${agent.task}`}
                onPress={() => setSelectedAgent(selectedAgent?.provider === agent.provider ? null : agent)}
                style={({ pressed }) => [styles.agentCard, selectedAgent?.provider === agent.provider && styles.agentSelected, pressed && styles.pressed]}
              >
                <View style={[styles.agentMark, { backgroundColor: agent.color }]}><Text style={styles.agentMarkText}>{agent.mark}</Text></View>
                <Text style={styles.agentName}>{agent.name}</Text>
                <Text style={styles.agentProvider}>{agent.provider}</Text>
                <Text style={styles.agentTask} numberOfLines={2}>{agent.task}</Text>
                <View style={styles.agentStatus}><View style={[styles.statusDot, agent.status === 'waiting' && styles.waitingDot]} /><Text style={styles.statusText}>{agent.status === 'working' ? '実行中' : agent.status === 'reviewing' ? '検査中' : '待機'}</Text></View>
              </Pressable>
            ))}
          </ScrollView>
          {selectedAgent && (
            <View style={styles.agentDetail}>
              <Text style={styles.agentDetailText}>{selectedAgent.provider}は「{selectedAgent.task}」を担当。作者とレビュアーは別プロバイダーに固定されています。</Text>
            </View>
          )}

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Production line</Text>
            <Text style={styles.sectionAction}>証拠がなければ公開しない</Text>
          </View>
          <View style={styles.panel}>
            {stages.map(([name, value, active], index) => (
              <View style={[styles.stage, index === stages.length - 1 && styles.stageLast]} key={String(name)}>
                <View style={[styles.stageIndicator, active ? styles.stageActive : styles.stageInactive]}>
                  <Text style={[styles.stageNumber, active && styles.stageNumberActive]}>{index < 2 ? '✓' : index + 1}</Text>
                </View>
                <View style={styles.stageCopy}><Text style={styles.stageName}>{name}</Text><Text style={styles.stageOwner}>{index % 2 ? 'OpenAI' : 'Anthropic'}</Text></View>
                <Text style={[styles.stageValue, active && index === 3 && styles.acidText]}>{value}</Text>
              </View>
            ))}
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>あなたの判断</Text>
            {!approved && <View style={styles.count}><Text style={styles.countText}>1</Text></View>}
          </View>
          <View style={[styles.approvalCard, approved && styles.approvedCard]}>
            <View style={styles.approvalTop}>
              <Text style={styles.approvalType}>{approved ? 'APPROVED' : 'PRODUCT DECISION'}</Text>
              <Text style={styles.approvalCost}>追加 ¥1,840</Text>
            </View>
            <Text style={styles.approvalTitle}>{approved ? 'PV制作を承認しました' : '30秒のローンチPVを制作する'}</Text>
            <Text style={styles.approvalBody}>{approved ? 'Geminiが構成を確認し、Seedanceへ映像制作を委任します。' : 'プレイ映像と生成素材から3案を制作。広告テストにも転用します。'}</Text>
            {!approved && (
              <View style={styles.approvalActions}>
                <Pressable accessibilityRole="button" style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}><Text style={styles.secondaryButtonText}>詳細</Text></Pressable>
                <Pressable accessibilityRole="button" onPress={approve} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}><Text style={styles.primaryButtonText}>承認する</Text></Pressable>
              </View>
            )}
          </View>
        </ScrollView>

        <View style={styles.tabBar}>
          {[['⌂', 'Overview'], ['⌁', 'Missions'], ['◫', 'Artifacts'], ['✓', 'Approvals']].map(([icon, label], index) => (
            <Pressable key={label} accessibilityRole="button" style={({ pressed }) => [styles.tab, pressed && styles.pressed]}>
              <Text style={[styles.tabIcon, index === 0 && styles.tabActive]}>{icon}</Text>
              <Text style={[styles.tabLabel, index === 0 && styles.tabActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  background: { flex: 1 },
  safe: { flex: 1 },
  content: { paddingHorizontal: 18, paddingTop: Platform.OS === 'android' ? 36 : 10, paddingBottom: 116 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 },
  brand: { color: '#F5F7F8', fontSize: 17, fontWeight: '800', letterSpacing: 1.2 },
  subtitle: { color: '#6D7881', fontSize: 8, fontWeight: '700', letterSpacing: 1.6, marginTop: 4 },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#242B30', alignItems: 'center', justifyContent: 'center', borderWidth: StyleSheet.hairlineWidth, borderColor: '#465058' },
  avatarText: { color: '#D9FF66', fontWeight: '800' },
  missionCard: { borderRadius: 24, padding: 20, borderWidth: StyleSheet.hairlineWidth, borderColor: '#46573A', overflow: 'hidden' },
  missionTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  livePill: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(12,16,12,.45)', paddingHorizontal: 9, paddingVertical: 6, borderRadius: 12 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#D9FF66', marginRight: 6 },
  liveText: { color: '#D9FF66', fontSize: 8, fontWeight: '800', letterSpacing: 1 },
  day: { color: '#9EAA94', fontSize: 9, fontWeight: '700', letterSpacing: .8 },
  missionTitle: { color: '#F7F9F6', fontSize: 27, lineHeight: 34, fontWeight: '700', letterSpacing: -.7, marginTop: 18 },
  missionMeta: { color: '#9BA597', fontSize: 11, marginTop: 8 },
  progressTrack: { height: 5, borderRadius: 3, backgroundColor: 'rgba(255,255,255,.1)', marginTop: 20, overflow: 'hidden' },
  progressFill: { height: 5, borderRadius: 3, backgroundColor: '#D9FF66' },
  metrics: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 19, paddingRight: 16 },
  metricValue: { color: '#F2F6ED', fontSize: 17, fontWeight: '700', fontVariant: ['tabular-nums'] },
  metricLabel: { color: '#869080', fontSize: 9, marginTop: 3 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 27, marginBottom: 12 },
  sectionTitle: { color: '#F1F4F6', fontSize: 17, fontWeight: '700', letterSpacing: -.2 },
  sectionAction: { color: '#747F88', fontSize: 9 },
  agentRow: { gap: 10, paddingRight: 20 },
  agentCard: { width: 136, minHeight: 167, borderRadius: 19, backgroundColor: '#151A1F', padding: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: '#2B333A' },
  agentSelected: { borderColor: '#D9FF66', backgroundColor: '#182018' },
  agentMark: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  agentMarkText: { color: '#FFFFFF', fontSize: 12, fontWeight: '900' },
  agentName: { color: '#F0F3F5', fontSize: 13, fontWeight: '700' },
  agentProvider: { color: '#76818A', fontSize: 9, marginTop: 2 },
  agentTask: { color: '#A8B0B6', fontSize: 10, lineHeight: 14, marginTop: 10, minHeight: 28 },
  agentStatus: { flexDirection: 'row', alignItems: 'center', marginTop: 11 },
  statusDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: '#D9FF66', marginRight: 5 },
  waitingDot: { backgroundColor: '#59636B' },
  statusText: { color: '#78838B', fontSize: 8 },
  agentDetail: { backgroundColor: '#171D20', padding: 13, borderRadius: 14, marginTop: 10 },
  agentDetailText: { color: '#9DA8AE', fontSize: 10, lineHeight: 15 },
  panel: { borderRadius: 20, backgroundColor: '#13181C', paddingHorizontal: 15, borderWidth: StyleSheet.hairlineWidth, borderColor: '#283038' },
  stage: { minHeight: 61, flexDirection: 'row', alignItems: 'center', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#262D33' },
  stageLast: { borderBottomWidth: 0 },
  stageIndicator: { width: 28, height: 28, borderRadius: 9, alignItems: 'center', justifyContent: 'center', marginRight: 11 },
  stageActive: { backgroundColor: '#28331F' },
  stageInactive: { backgroundColor: '#20262B' },
  stageNumber: { color: '#68737B', fontSize: 10, fontWeight: '700' },
  stageNumberActive: { color: '#D9FF66' },
  stageCopy: { flex: 1 },
  stageName: { color: '#E5E9EB', fontSize: 12, fontWeight: '600' },
  stageOwner: { color: '#68737B', fontSize: 8, marginTop: 3 },
  stageValue: { color: '#657079', fontSize: 9, fontVariant: ['tabular-nums'] },
  acidText: { color: '#D9FF66' },
  count: { width: 19, height: 19, borderRadius: 10, backgroundColor: '#FF765C', alignItems: 'center', justifyContent: 'center' },
  countText: { color: '#FFFFFF', fontSize: 10, fontWeight: '800' },
  approvalCard: { borderRadius: 20, backgroundColor: '#1C1817', padding: 17, borderWidth: StyleSheet.hairlineWidth, borderColor: '#514137' },
  approvedCard: { backgroundColor: '#172019', borderColor: '#3B553B' },
  approvalTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  approvalType: { color: '#FFB27A', fontSize: 8, fontWeight: '800', letterSpacing: 1 },
  approvalCost: { color: '#8E817B', fontSize: 9 },
  approvalTitle: { color: '#F4F0EE', fontSize: 16, fontWeight: '700', marginTop: 13 },
  approvalBody: { color: '#988E89', fontSize: 10, lineHeight: 16, marginTop: 7 },
  approvalActions: { flexDirection: 'row', gap: 9, marginTop: 16 },
  secondaryButton: { flex: 1, minHeight: 43, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: '#282321' },
  secondaryButtonText: { color: '#B2AAA6', fontSize: 12, fontWeight: '600' },
  primaryButton: { flex: 1.5, minHeight: 43, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F1F3EE' },
  primaryButtonText: { color: '#171A16', fontSize: 12, fontWeight: '700' },
  pressed: { opacity: .72, transform: [{ scale: .98 }] },
  tabBar: { position: 'absolute', left: 12, right: 12, bottom: Platform.OS === 'ios' ? 8 : 12, height: 72, borderRadius: 25, backgroundColor: 'rgba(26,31,35,.96)', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', borderWidth: StyleSheet.hairlineWidth, borderColor: '#394149', paddingBottom: Platform.OS === 'ios' ? 5 : 0 },
  tab: { width: 74, alignItems: 'center', justifyContent: 'center', paddingVertical: 8 },
  tabIcon: { color: '#65717A', fontSize: 18, marginBottom: 4 },
  tabLabel: { color: '#65717A', fontSize: 8, fontWeight: '600' },
  tabActive: { color: '#D9FF66' },
});
