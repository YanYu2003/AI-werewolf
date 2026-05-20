import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

export default function HomePage() {
  const navigate = useNavigate();
  const [playerCount, setPlayerCount] = useState(8);
  const [humanName, setHumanName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleCreate(mode: 'ai' | 'mixed') {
    setLoading(true);
    setError('');
    try {
      const req = {
        player_count: playerCount,
        human_players: mode === 'mixed' && humanName.trim()
          ? [{ name: humanName.trim() }]
          : [],
        config: { enable_human: mode === 'mixed', auto_start: true },
      };
      const res = await api.createGame(req);
      navigate(`/game/${res.game_id}`);
    } catch (e: any) {
      setError(e.message || '创建失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ textAlign: 'center', paddingTop: 80 }}>
      <h1 style={{ fontSize: '2rem', marginBottom: 8 }}>🐺 AI 狼人杀</h1>
      <p style={{ color: '#666', marginBottom: 32 }}>
        多智能体协作与博弈系统
      </p>

      <div style={{ marginBottom: 16 }}>
        <label>玩家数量：</label>
        <input
          type="number"
          min={2}
          max={12}
          value={playerCount}
          onChange={(e) => setPlayerCount(Number(e.target.value))}
          style={{ width: 60, padding: 4, fontSize: 16, textAlign: 'center' }}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <input
          type="text"
          placeholder="输入你的名字（人机混战）"
          value={humanName}
          onChange={(e) => setHumanName(e.target.value)}
          style={{ padding: '8px 12px', fontSize: 14, width: 240 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 16, justifyContent: 'center' }}>
        <button
          onClick={() => handleCreate('ai')}
          disabled={loading}
          style={btnStyle}
        >
          创建纯 AI 对局
        </button>
        <button
          onClick={() => handleCreate('mixed')}
          disabled={loading || !humanName.trim()}
          style={{ ...btnStyle, opacity: !humanName.trim() ? 0.5 : 1 }}
        >
          创建人机混战
        </button>
      </div>

      {error && <p style={{ color: 'red', marginTop: 16 }}>{error}</p>}
      {loading && <p style={{ marginTop: 16 }}>创建中...</p>}
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '10px 24px',
  fontSize: 15,
  cursor: 'pointer',
  backgroundColor: '#1a73e8',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
};
