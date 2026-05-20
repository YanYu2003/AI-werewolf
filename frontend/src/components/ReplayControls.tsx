interface Props {
  currentIndex: number;
  totalEvents: number;
  onReset: () => void;
  onNext: () => void;
}

export default function ReplayControls({ currentIndex, totalEvents, onReset, onNext }: Props) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '8px 0' }}>
      <button onClick={onReset} disabled={currentIndex === 0} style={btnStyle}>
        ⏮ 重置
      </button>
      <button onClick={onNext} disabled={currentIndex >= totalEvents - 1} style={btnStyle}>
        下一步 ⏭
      </button>
      <span style={{ fontSize: 13, color: '#666' }}>
        {currentIndex + 1} / {totalEvents}
      </span>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: '6px 14px', fontSize: 13, cursor: 'pointer',
  backgroundColor: '#1a73e8', color: '#fff', border: 'none', borderRadius: 4,
};
