import asyncio
import json
import os
import websockets

CONNECTED = set()
GAMES = {}  # room_id: game_state


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


async def handler(websocket):
    global waiting_player
    CONNECTED.add(websocket)

    try:
        # Поиск пары для игры
        if waiting_player is None:
            waiting_player = websocket
            await websocket.send(
                json.dumps({
                    "type": "waiting",
                    "msg": "Ожидание второго игрока..."
                }))
            while waiting_player == websocket:
                await asyncio.sleep(0.5)
        else:
            p1 = waiting_player
            p2 = websocket
            waiting_player = None

            game = Game(p1, p2)
            GAMES[p1] = (game, p2)
            GAMES[p2] = (game, p1)

            # Оповещаем игроков о начале
            await p1.send(
                json.dumps({
                    "type": "init",
                    "symbol": "X",
                    "turn": "X",
                    "board": game.board
                }))
            await p2.send(
                json.dumps({
                    "type": "init",
                    "symbol": "O",
                    "turn": "X",
                    "board": game.board
                }))

        # Обработка сообщений от клиента
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "move":
                if websocket in GAMES:
                    game, opponent = GAMES[websocket]
                    symbol = game.players[websocket]

                    if game.make_move(data["index"], symbol):
                        winner = game.check_winner()
                        state = {
                            "type": "update",
                            "board": game.board,
                            "turn": game.turn,
                            "winner": winner,
                        }
                        await websocket.send(json.dumps(state))
                        await opponent.send(json.dumps(state))

    except websockets.ConnectionClosed:
        pass
    finally:
        CONNECTED.remove(websocket)
        if waiting_player == websocket:
            waiting_player = None


async def main():
    # Render передает порт в переменной окружения PORT
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Сервер запущен на порту {port}")
        await asyncio.Future()  # Бесконечный цикл


if __name__ == "__main__":
    asyncio.run(main())
