import { useState, useEffect } from 'react';
import { api } from '../api/client';

interface Props {
  gameId: number;
  playerId: number;
  onAction: () => void;
}

export default function HumanActionPanel({ gameId, playerId, onAction }: Props) {
  const [view, setView] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [actionType, setActionType] = useState('');
  const [targetId, setTargetId] = useState('');
  const [content, setContent] = useState('');
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  // 以后端返回的 legal_actions 为准
  const legalActions: string[] = view?.legal_actions || [];

  const fetchView = async () => {
    setLoading(true);
    setError('');
    try {
      const v = await api.getPlayerView(gameId, playerId);
      setView(v);
      // 重置动作选择
      const actions: string[] = v?.legal_actions || [];
      if (actions.length > 0 && !actions.includes(actionType)) {
        setActionType(actions[0]);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchView();
  }, [gameId, playerId]);

  async function handleSubmit() {
    setResult(null);
    try {
      const res = await api.humanAction(gameId, playerId, {
        action_type: actionType,
        target_id: targetId ? Number(targetId) : null,
        content: content || null,
      });
      setResult(res);
      if (res.accepted) {
        // 动作被接受后刷新视角和父组件状态
        await fetchView();
        onAction();
      }
    } catch (e: any) {
      setResult({ accepted: false, reason: e.message });
    }
  }

  // 当前未轮到 human 行动
  if (legalActions.length === 0 && !loading) {
    return (
      <div style={{ margin: '12px 0', padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
        <p style={{ fontSize: 13, color: '#666' }}>
          ⏳ 等待其他玩家行动
          {view?.self_player?.role && (
            <span>（你的角色：{view.self_player.role}）</span>
          )}
        </p>
        <button onClick={fetchView} style={btnStyle}>刷新</button>
      </div>
    );
  }

  const isWaiting = legalActions.length === 0;

  return (
    <div style={{ margin: '12px 0', padding: 12, background: '#fff3e0', borderRadius: 6 }}>
      <h4 style={{ margin: '0 0 8px' }}>
        🎮 操作面板
        {view?.self_player && (
          <span style={{ fontSize: 13, color: '#666', marginLeft: 8 }}>
            #{view.self_player.player_id} {view.self_player.name}
            {' | '}角色：{view.self_player.role || '?'}
            {' | '}阶段：{view?.phase || ''}
            {view?.day_stage ? ` / ${view.day_stage}` : ''}
            {view?.night_stage ? ` / ${view.night_stage}` : ''}
          </span>
        )}
      </h4>

      {isWaiting ? (
        <p style={{ fontSize: 13, color: '#999' }}>⏳ 等待其他玩家行动</p>
      ) : (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            style={inputStyle}
          >
            {legalActions.map((a: string) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>

          <input
            type="number"
            placeholder="目标 ID（可选）"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            style={{ ...inputStyle, width: 100 }}
          />

          <input
            type="text"
            placeholder="发言内容（可选）"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={{ ...inputStyle, width: 200 }}
          />

          <button
            onClick={handleSubmit}
            disabled={loading}
            style={{ ...btnStyle, backgroundColor: '#ff9800' }}
          >
            提交
          </button>

          <button onClick={fetchView} disabled={loading} style={{ ...btnStyle, backgroundColor: '#757575' }}>
            刷新
          </button>
        </div>
      )}

      {error && <p style={{ fontSize: 13, color: '#f44336', marginTop: 8 }}>❌ {error}</p>}

      {result && (
        <p style={{
          fontSize: 13,
          color: result.accepted ? '#4caf50' : '#f44336',
          marginTop: 8,
        }}>
          {result.accepted ? '✅ 已提交' : `❌ ${result.reason || '动作被拒绝'}`}
        </p>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: '6px 8px', fontSize: 13, borderRadius: 4, border: '1px solid #ccc',
};
const btnStyle: React.CSSProperties = {
  padding: '6px 16px', fontSize: 13, color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer',
};
