import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { GameWebSocket } from '../api/ws';
import type { PublicGameState } from '../types/game';
import GameStatusBar from '../components/GameStatusBar';
import PlayerBoard from '../components/PlayerBoard';
import EventTimeline from '../components/EventTimeline';
import HumanActionPanel from '../components/HumanActionPanel';

export default function GamePage() {
  const { gameId } = useParams<{ gameId: string }>();
  const gid = Number(gameId);
  const [state, setState] = useState<PublicGameState | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const [humanPlayerId, setHumanPlayerId] = useState<number>(0);
  const wsRef = useRef<GameWebSocket | null>(null);

  const fetchState = useCallback(async () => {
    try {
      const s = await api.getGameState(gid);
      setState(s);
      setEvents(s?.public_events || []);
    } catch (e: any) {
      setError(e.message);
    }
  }, [gid]);

  useEffect(() => {
    fetchState();
    const ws = new GameWebSocket(gid, (data) => {
      if (data.type === 'snapshot') {
        const s = data.payload?.state;
        setState(s || null);
      } else if (data.type === 'event') {
        setEvents((prev) => [...prev, data.event]);
      }
    });
    ws.connect();
    wsRef.current = ws;
    return () => ws.disconnect();
  }, [gid, fetchState]);

  async function handleStep() {
    setLoading(true);
    setError('');
    try {
      await api.stepGame(gid);
      await fetchState();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAutoRun() {
    setLoading(true);
    setError('');
    try {
      const res = await api.autoRun(gid, 100);
      await fetchState();
      if (res.stopped_reason === 'waiting_for_human') {
        setError('等待玩家操作...');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!state) return <p>加载中...</p>;

  const isFinished = state.status === 'finished';
  const humanPlayers = state.players.filter((p) => p.type === 'human');

  return (
    <div>
      <GameStatusBar state={state} wsConnected={wsConnected} />
      <div style={{ display: 'flex', gap: 16, margin: '12px 0' }}>
        <button onClick={handleStep} disabled={loading || isFinished} style={btnStyle}>
          推进一步
        </button>
        <button onClick={handleAutoRun} disabled={loading || isFinished} style={btnStyle}>
          自动运行
        </button>
        <button onClick={fetchState} disabled={loading} style={btnStyle}>
          刷新状态
        </button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {/* 玩家 ID 选择器 */}
      {humanPlayers.length > 0 && (
        <div style={{ marginBottom: 12, fontSize: 14 }}>
          <label>选择你的玩家 ID：</label>
          <select
            value={humanPlayerId}
            onChange={(e) => setHumanPlayerId(Number(e.target.value))}
            style={{ marginLeft: 8, padding: '4px 8px' }}
          >
            <option value={0}>-- 选择 --</option>
            {humanPlayers.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                #{p.player_id} {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <PlayerBoard players={state.players} />
      <EventTimeline events={events} />

      {!isFinished && humanPlayerId > 0 && (
        <HumanActionPanel
          gameId={gid}
          playerId={humanPlayerId}
          onAction={fetchState}
        />
      )}

      {!isFinished && humanPlayerId === 0 && humanPlayers.length > 0 && (
        <p style={{ color: '#999', fontSize: 13 }}>请在上方选择你的玩家 ID 以显示操作面板</p>
      )}

      {!isFinished && humanPlayers.length === 0 && (
        <p style={{ color: '#999', fontSize: 13 }}>纯 AI 对局，无人类玩家操作面板</p>
      )}

      {isFinished && (
        <div style={{ marginTop: 16, padding: 12, background: '#e8f5e9', borderRadius: 6 }}>
          <strong>游戏结束！</strong>
          {state.winner_team === 'villagers' ? '👨‍🌾 好人阵营获胜' : '🐺 狼人阵营获胜'}
          <div style={{ marginTop: 8 }}>
            <a href={`/replay/${gid}`}>查看回放 →</a>
          </div>
        </div>
      )}
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
