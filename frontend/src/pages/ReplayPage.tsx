import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ReplayResponse, ReplayEvent } from '../types/game';
import ReplayControls from '../components/ReplayControls';
import RoleRevealPanel from '../components/RoleRevealPanel';

export default function ReplayPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const gid = Number(gameId);
  const navigate = useNavigate();
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getReplay(gid).then(setReplay).catch(console.error).finally(() => setLoading(false));
  }, [gid]);

  if (loading) return <p>加载回放...</p>;
  if (!replay) return <p>回放数据未找到</p>;

  const events = replay.events;
  const displayedEvents = events.slice(0, currentIndex + 1);
  const currentEvent = events[currentIndex] || null;
  const isEnd = currentIndex >= events.length - 1 && replay.status === 'finished';

  return (
    <div>
      <h2>🎬 对局回放 — 第 {gid} 局</h2>
      <div style={{ marginBottom: 8 }}>
        {replay.winner_team === 'villagers' ? '👨‍🌾 好人胜' : '🐺 狼人胜'}
        {' | '}共 {events.length} 个事件
      </div>

      <ReplayControls
        currentIndex={currentIndex}
        totalEvents={events.length}
        onReset={() => setCurrentIndex(0)}
        onNext={() => setCurrentIndex(Math.min(currentIndex + 1, events.length - 1))}
      />

      <div style={{ marginTop: 16, border: '1px solid #ddd', borderRadius: 6, padding: 12, minHeight: 300, maxHeight: 500, overflowY: 'auto' }}>
        {displayedEvents.map((ev, i) => (
          <div
            key={i}
            style={{
              padding: '6px 8px',
              margin: '2px 0',
              backgroundColor: i === currentIndex ? '#e3f2fd' : 'transparent',
              borderRadius: 4,
              fontSize: 13,
            }}
          >
            <strong>[{ev.round}.{ev.phase}]</strong>{' '}
            <span style={{ color: '#666' }}>{ev.event_type}</span>
            {ev.public_payload?.content && <span> — {ev.public_payload.content}</span>}
          </div>
        ))}
      </div>

      {isEnd && replay.final_roles?.length > 0 && (
        <RoleRevealPanel roles={replay.final_roles} />
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button onClick={() => navigate(`/game/${gid}`)} style={btnStyle}>
          返回游戏
        </button>
        <button onClick={() => navigate('/')} style={btnStyle}>
          回到首页
        </button>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '8px 16px',
  fontSize: 14,
  cursor: 'pointer',
  backgroundColor: '#1a73e8',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
};
