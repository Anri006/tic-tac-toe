import asyncio
import json
import os
from aiohttp import web

CONNECTED = set()
GAMES = {}  # ws: (game, opponent_ws)


class Game:

    def __init__(self, p1, p2):
        self.players = {p1: "X", p2: "O"}
        self.board = [""] * 9
        self.turn = "X"

    def make_move(self, index, symbol):
        if self.board[index] == "" and self.turn == symbol:
            self.board[index] = symbol
            self.turn = "O" if symbol == "X" else "X"
            return True
        return False

    def check_winner(self):
        combo = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7),
                 (2, 5, 8), (0, 4, 8), (2, 4, 6)]
        for a, b, c in combo:
            if self.board[a] and self.board[a] == self.board[b] == self.board[
                    c]:
                return self.board[a]
        if "" not in self.board:
            return "Draw"
        return None


waiting_player = None


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    global waiting_player
    CONNECTED.add(ws)

    try:
        # Логика поиска соперника
        if waiting_player is None:
            waiting_player = ws
            await ws.send_str(
                json.dumps({
                    "type": "waiting",
                    "msg": "Ожидание второго игрока..."
                }))
            while waiting_player == ws:
                await asyncio.sleep(0.5)
        else:
            p1 = waiting_player
            p2 = ws
            waiting_player = None

            game = Game(p1, p2)
            GAMES[p1] = (game, p2)
            GAMES[p2] = (game, p1)

            await p1.send_str(
                json.dumps({
                    "type": "init",
                    "symbol": "X",
                    "turn": "X",
                    "board": game.board
                }))
            await p2.send_str(
                json.dumps({
                    "type": "init",
                    "symbol": "O",
                    "turn": "X",
                    "board": game.board
                }))

        # Обработка сообщений от клиента
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "move" and ws in GAMES:
                    game, opponent = GAMES[ws]
                    symbol = game.players[ws]

                    if game.make_move(data["index"], symbol):
                        winner = game.check_winner()
                        state = {
                            "type": "update",
                            "board": game.board,
                            "turn": game.turn,
                            "winner": winner,
                        }
                        await ws.send_str(json.dumps(state))
                        await opponent.send_str(json.dumps(state))

    except Exception as e:
        print(f"Ошибка WebSocket: {e}")
    finally:
        CONNECTED.remove(ws)
        if waiting_player == ws:
            waiting_player = None
        if ws in GAMES:
            _, opponent = GAMES[ws]
            del GAMES[ws]

    return ws


# Принимаем соединения и на главный роут, и на /ws
app = web.Application()
app.router.add_get("/", websocket_handler)
app.router.add_get("/ws", websocket_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    web.run_app(app, host="0.0.0.0", port=port)
