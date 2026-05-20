import type { PlayerPublicInfo } from '../types/game';

interface Props {
  players: PlayerPublicInfo[];
}

export default function PlayerBoard({ players }: Props) {
  return (
    <div style={{ margin: '12px 0' }}>
      <h3 style={{ margin: '0 0 8px' }}>玩家列表</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
        {players.map((p) => (
          <div
            key={p.player_id}
            style={{
              padding: 8, borderRadius: 6, fontSize: 13,
              backgroundColor: p.alive ? '#e8f5e9' : '#fce4ec',
              opacity: p.alive ? 1 : 0.6,
              border: '1px solid #ddd',
            }}
          >
            <div><strong>#{p.player_id}</strong> {p.name}</div>
            <div style={{ fontSize: 12, color: '#666' }}>
              {p.type === 'human' ? '🧑 人类' : '🤖 AI'}
              {' | '}{p.alive ? '存活' : '死亡'}
            </div>
            {p.role && <div style={{ fontSize: 12, color: '#1a73e8' }}>🎭 {p.role}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
