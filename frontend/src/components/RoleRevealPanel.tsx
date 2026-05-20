import type { FinalRoleInfo } from '../types/game';

interface Props {
  roles: FinalRoleInfo[];
}

export default function RoleRevealPanel({ roles }: Props) {
  return (
    <div style={{ marginTop: 16, padding: 12, background: '#f3e5f5', borderRadius: 6 }}>
      <h4 style={{ margin: '0 0 8px' }}>🎭 最终角色公布</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 6 }}>
        {roles.map((r) => (
          <div key={r.player_id} style={{ fontSize: 13, padding: 4 }}>
            <strong>#{r.player_id}</strong> {r.name} — {roleIcon(r.role)} {r.role}
          </div>
        ))}
      </div>
    </div>
  );
}

function roleIcon(role: string): string {
  const map: Record<string, string> = {
    werewolf: '🐺', seer: '🔮', witch: '🧪',
    hunter: '🏹', villager: '👨‍🌾',
  };
  return map[role] || '❓';
}
