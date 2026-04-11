"use strict";
const WINNING_COMBOS = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8], // rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8], // cols
    [0, 4, 8], [2, 4, 6], // diagonals
];
const state = {
    board: Array(9).fill(null),
    currentPlayer: "X",
    winner: null,
    isDraw: false,
    gameOver: false,
    scores: { X: 0, O: 0, draws: 0 },
    winLine: null,
};
function checkWinner(board) {
    for (const combo of WINNING_COMBOS) {
        const [a, b, c] = combo;
        if (board[a] && board[a] === board[b] && board[a] === board[c]) {
            return { winner: board[a], line: combo };
        }
    }
    return null;
}
function checkDraw(board) {
    return board.every((cell) => cell !== null);
}
function getStatusText() {
    if (state.winner) {
        return `Player ${state.winner} wins!`;
    }
    if (state.isDraw) {
        return "It's a draw!";
    }
    return `Player ${state.currentPlayer}'s turn`;
}
function renderBoard() {
    const cells = document.querySelectorAll(".cell");
    cells.forEach((cell, index) => {
        var _a;
        const value = state.board[index];
        cell.textContent = value !== null && value !== void 0 ? value : "";
        cell.className = "cell";
        if (value === "X")
            cell.classList.add("x");
        if (value === "O")
            cell.classList.add("o");
        if (state.gameOver)
            cell.classList.add("disabled");
        if ((_a = state.winLine) === null || _a === void 0 ? void 0 : _a.includes(index))
            cell.classList.add("winning");
    });
    const status = document.getElementById("status");
    status.textContent = getStatusText();
    status.className = "status";
    if (state.winner)
        status.classList.add("winner-text");
    if (state.isDraw)
        status.classList.add("draw-text");
    document.getElementById("score-x").textContent = String(state.scores.X);
    document.getElementById("score-o").textContent = String(state.scores.O);
    document.getElementById("score-draws").textContent = String(state.scores.draws);
    const turnIndicator = document.getElementById("turn-indicator");
    turnIndicator.textContent = state.currentPlayer;
    turnIndicator.className = `turn-indicator ${state.currentPlayer.toLowerCase()}`;
}
function handleCellClick(index) {
    if (state.board[index] !== null || state.gameOver)
        return;
    state.board[index] = state.currentPlayer;
    const result = checkWinner(state.board);
    if (result) {
        state.winner = result.winner;
        state.winLine = result.line;
        state.gameOver = true;
        state.scores[result.winner]++;
    }
    else if (checkDraw(state.board)) {
        state.isDraw = true;
        state.gameOver = true;
        state.scores.draws++;
    }
    else {
        state.currentPlayer = state.currentPlayer === "X" ? "O" : "X";
    }
    renderBoard();
}
function resetGame() {
    state.board = Array(9).fill(null);
    state.currentPlayer = "X";
    state.winner = null;
    state.isDraw = false;
    state.gameOver = false;
    state.winLine = null;
    renderBoard();
}
function resetScores() {
    state.scores = { X: 0, O: 0, draws: 0 };
    resetGame();
}
function init() {
    const board = document.getElementById("board");
    board.innerHTML = "";
    for (let i = 0; i < 9; i++) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.addEventListener("click", () => handleCellClick(i));
        board.appendChild(cell);
    }
    document.getElementById("reset-btn").addEventListener("click", resetGame);
    document.getElementById("reset-scores-btn").addEventListener("click", resetScores);
    renderBoard();
}
document.addEventListener("DOMContentLoaded", init);
