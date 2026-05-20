type MessageHandler = (data: any) => void;

export class GameWebSocket {
  private ws: WebSocket | null = null;
  private gameId: number;
  private onMessage: MessageHandler;
  private onDisconnect: (() => void) | null = null;

  constructor(gameId: number, onMessage: MessageHandler) {
    this.gameId = gameId;
    this.onMessage = onMessage;
  }

  connect(): void {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/games/${this.gameId}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log(`WS connected to game ${this.gameId}`);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    this.ws.onclose = () => {
      console.log(`WS disconnected from game ${this.gameId}`);
      this.onDisconnect?.();
    };

    this.ws.onerror = (err) => {
      console.error("WS error:", err);
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  onDisconnectHandler(handler: () => void): void {
    this.onDisconnect = handler;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
