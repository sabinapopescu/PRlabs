/**
 * Retrieve the current board state as seen by a player.
 * Shows face-up cards with their pictures, face-down cards as 'down',
 * and empty spaces as 'none'.
 *
 * @param board the game board to observe
 * @param playerId identifier of the player viewing the board
 * @returns textual representation of the current board state
 * @throws Error when not yet implemented
 */
export async function look(board, playerId) {
    board.registerPlayer(playerId);
    return board.render(playerId);
}
/**
 * Attempt to flip a card face-up for the specified player.
 * May block if another player has control of this card.
 * Card stays face-up under player control until flipped down.
 *
 * @param board the game board
 * @param playerId identifier of the player attempting the flip
 * @param row the row position of the card (0-indexed)
 * @param column the column position of the card (0-indexed)
 * @returns board state after the flip operation
 * @throws Error if the position is invalid, card already face-up, or cell is empty
 */
export async function flip(board, playerId, row, column) {
    board.registerPlayer(playerId);
    await board.flipUp(playerId, row, column);
    return board.render(playerId);
}
/**
 * Transform all card pictures on the board using a mapping function.
 * Empty cells remain unchanged.
 *
 * @param board the game board
 * @param playerId identifier of the player performing the transformation
 * @param f asynchronous transformation function from old picture to new picture
 * @returns board state after applying the transformation
 */
export async function map(board, playerId, f) {
    board.registerPlayer(playerId);
    await board.map(f);
    return board.render(playerId);
}
/**
 * Monitor the board until a change occurs.
 * Blocks until another player modifies the board state, then returns the updated state.
 *
 * @param board the game board to monitor
 * @param playerId identifier of the player watching
 * @returns the updated board state when a change is detected
 */
export async function watch(board, playerId) {
    board.registerPlayer(playerId);
    const { promise, resolve } = Promise.withResolvers();
    board.addChangeWatcher(playerId, resolve);
    return promise;
}
//# sourceMappingURL=commands.js.map