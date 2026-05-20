/** Game-related TypeScript types matching backend API models */

export interface PlayerPublicInfo {
  player_id: number;
  name: string;
  type: "human" | "ai";
  alive: boolean;
  role: string | null;
  revealed_role: string | null;
}

export interface GameListItem {
  game_id: number;
  status: string;
  current_round: number;
  current_phase: string;
  winner_team: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicGameState {
  game_id: number;
  status: string;
  current_round: number;
  current_phase: string;
  day_stage: string | null;
  night_stage: string | null;
  winner_team: string | null;
  players: PlayerPublicInfo[];
  public_events: PublicEvent[];
  available_actions: string[];
}

export interface PublicEvent {
  event_type: string;
  actor_id: number;
  role: string;
  content: string;
  round: number;
  timestamp: string;
}

export interface CreateGameRequest {
  player_count: number;
  human_players: { name: string }[];
  config: { enable_human: boolean; auto_start: boolean };
}

export interface CreateGameResponse {
  game_id: number;
  status: string;
  players: PlayerPublicInfo[];
  current_round: number;
  current_phase: string;
}

export interface StepResponse {
  game_id: number;
  status: string;
  applied_events: any[];
  current_round: number;
  current_phase: string;
  waiting_for_human: boolean;
  pending_player_id: number | null;
  legal_actions: string[];
}

export interface AutoRunResponse {
  game_id: number;
  status: string;
  winner_team: string | null;
  steps: number;
  stopped_reason: string;
}

export interface HumanActionRequest {
  action_type: string;
  target_id: number | null;
  content: string | null;
}

export interface HumanActionResponse {
  accepted: boolean;
  game_id: number;
  player_id: number;
  action: any;
  next_state: PublicGameState | null;
  reason: string;
}

export interface ReplayEvent {
  index: number;
  round: number;
  phase: string;
  event_type: string;
  public_payload: any;
  timestamp: string;
}

export interface FinalRoleInfo {
  player_id: number;
  name: string;
  role: string;
}

export interface ReplayResponse {
  game_id: number;
  status: string;
  winner_team: string | null;
  events: ReplayEvent[];
  final_roles: FinalRoleInfo[];
}
