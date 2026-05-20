import type {
  CreateGameRequest,
  CreateGameResponse,
  PublicGameState,
  StepResponse,
  AutoRunResponse,
  HumanActionRequest,
  HumanActionResponse,
  ReplayResponse,
  GameListItem,
} from "../types/game";

const BASE = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  createGame(req: CreateGameRequest): Promise<CreateGameResponse> {
    return request("/games", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  listGames(): Promise<{ games: GameListItem[] }> {
    return request("/games");
  },

  getGameState(gameId: number): Promise<PublicGameState> {
    return request(`/games/${gameId}/state`);
  },

  getPlayerView(gameId: number, playerId: number): Promise<any> {
    return request(`/games/${gameId}/players/${playerId}/view`);
  },

  stepGame(gameId: number): Promise<StepResponse> {
    return request(`/games/${gameId}/step`, { method: "POST" });
  },

  autoRun(gameId: number, maxSteps = 200): Promise<AutoRunResponse> {
    return request(`/games/${gameId}/auto-run`, {
      method: "POST",
      body: JSON.stringify({ max_steps: maxSteps }),
    });
  },

  humanAction(
    gameId: number,
    playerId: number,
    req: HumanActionRequest
  ): Promise<HumanActionResponse> {
    return request(`/games/${gameId}/players/${playerId}/actions`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  getLogs(gameId: number): Promise<any> {
    return request(`/games/${gameId}/logs`);
  },

  getReplay(gameId: number): Promise<ReplayResponse> {
    return request(`/games/${gameId}/replay`);
  },
};
