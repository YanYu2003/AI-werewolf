import type { PublicGameState } from '../types/game';

interface Props {
  state: PublicGameState;
  wsConnected?: boolean;
}

export default function GameStatusBar({ state, wsConnected }: Props) {
  const s = state;
  return (
    <div style={{
      display: 'flex', gap: 16, alignItems: 'center',
      padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, fontSize: 14,
    }}>
      <strong>🎮 #{s.game_id}</strong>
      <span>回合: {s.current_round}</span>
      <span>阶段: {s.current_phase}{s.day_stage ? ` / ${s.day_stage}` : ''}{s.night_stage ? ` / ${s.night_stage}` : ''}</span>
      <span style={{ marginLeft: 'auto', color: wsConnected ? '#4caf50' : '#999' }}>
        {wsConnected ? '🟢 已连接' : '⚪ 未连接'}
      </span>
    </div>
  );
}
