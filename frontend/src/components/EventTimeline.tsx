interface EventItem {
  event_type: string;
  actor_id: number;
  role: string;
  content: string;
  round: number;
  timestamp: string;
}

interface Props {
  events: any[];
}

export default function EventTimeline({ events }: Props) {
  if (!events.length) {
    return <p style={{ color: '#999', fontSize: 13 }}>暂无事件</p>;
  }

  return (
    <div style={{ margin: '12px 0' }}>
      <h3 style={{ margin: '0 0 8px' }}>事件流</h3>
      <div style={{
        border: '1px solid #ddd', borderRadius: 6, padding: 8,
        maxHeight: 300, overflowY: 'auto', fontSize: 13,
      }}>
        {events.map((ev, i) => (
          <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
            <span style={{ color: '#999' }}>[{ev.round || ''}]</span>{' '}
            <span style={{ color: '#1a73e8' }}>{eventLabel(ev.event_type)}</span>
            {ev.content && <span> — {ev.content}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function eventLabel(type: string): string {
  const map: Record<string, string> = {
    announce_death: '💀 死亡公告',
    night_resolve: '🌙 夜晚结算',
    vote_result: '🗳️ 投票结果',
    speak: '💬 发言',
    game_over: '🏁 游戏结束',
    werewolf_kill_resolved: '🐺 狼人击杀',
  };
  return map[type] || type;
}
