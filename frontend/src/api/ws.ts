type MessageHandler = (data: any) => void;

interface GameWebSocketOptions {
  onMessage: MessageHandler;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export class GameWebSocket {
  private ws: WebSocket | null = null;
  private gameId: number;
  private options: GameWebSocketOptions;

  constructor(gameId: number, options: GameWebSocketOptions) {
    this.gameId = gameId;
    this.options = options;
  }

  connect(): void {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/games/${this.gameId}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log(`WS connected to game ${this.gameId}`);
      this.options.onConnect?.();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.options.onMessage(data);
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    this.ws.onclose = () => {
      console.log(`WS disconnected from game ${this.gameId}`);
      this.options.onDisconnect?.();
    };

    this.ws.onerror = (err) => {
      console.error("WS error:", err);
      this.options.onDisconnect?.();
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
