/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from "node:assert";
import fs from "node:fs";

/**
 * A mutable Memory Scramble game board that supports concurrent players.
 *
 * The board consists of a grid of spaces that may contain cards.
 * Cards can be face-down, face-up, or removed from the board.
 * Players can control cards and attempt to match pairs.
 */

type CardState = "none" | "face-up" | "face-down";

type Spot = {
  card: string | undefined;
  state: CardState;
  controller: string | undefined;
  // Waiters for this card - resolved when card becomes available
  waiters: Array<() => void>;
};

/** Player state tracking */
type PlayerState = {
  firstCard: { row: number; col: number } | undefined;
  previousCards: Array<{ row: number; col: number }>;
};

export class Board {
  private readonly rows: number;
  private readonly cols: number;
  private readonly grid: Spot[][];
  private readonly players: Map<string, PlayerState>;
  // Watchers waiting for board changes
  private readonly changeWatchers: Array<() => void>;

  // Abstraction function:
  //   AF(rows, cols, grid, players, changeWatchers) = a Memory Scramble game board with dimensions rows x cols
  //     where grid[r][c] represents the spot at position (r, c):
  //       - grid[r][c].card is the card string at that position, or undefined if no card
  //       - grid[r][c].state is 'none' if no card, 'face-down' if card is face down, 'face-up' if face up
  //       - grid[r][c].controller is the player ID controlling this card, or undefined if not controlled
  //     and players maps each player ID to their game state:
  //       - firstCard is the position of the first card they're trying to match, or undefined
  //       - previousCards are the cards from their last unsuccessful match attempt
  //
  // Representation invariant:
  //   - rows > 0, cols > 0
  //   - grid.length === rows
  //   - for all r in [0, rows): grid[r].length === cols
  //   - for all spots in grid:
  //       - if spot.state === 'none', then spot.card === undefined and spot.controller === undefined
  //       - if spot.state === 'face-down', then spot.card !== undefined and spot.controller === undefined
  //       - if spot.state === 'face-up', then spot.card !== undefined
  //       - if spot.controller !== undefined, then spot.state === 'face-up'
  //       - spot.waiters is an array of callback functions
  //   - for all player states:
  //       - if firstCard is defined, then grid[firstCard.row][firstCard.col].controller === playerID
  //       - all positions in previousCards refer to valid grid positions
  //   - no two players can control the same card
  //
  // Safety from rep exposure:
  //   - all fields are private and readonly (except grid contents which are mutable)
  //   - rows, cols are immutable numbers
  //   - grid is never returned directly; only defensive copies or string representations
  //   - players Map is never returned directly
  //   - all methods return strings or promises, never mutable rep components

  /**
   * Create a new Memory Scramble board.
   *
   * @param rows number of rows in the board, must be > 0
   * @param cols number of columns in the board, must be > 0
   * @param cards array of card strings to place on the board, must have exactly rows * cols elements
   */
  private constructor(rows: number, cols: number, cards: string[]) {
    this.rows = rows;
    this.cols = cols;
    this.players = new Map();
    this.changeWatchers = [];

    // Initialize grid with face-down cards
    this.grid = [];
    let cardIndex = 0;
    for (let r = 0; r < rows; r++) {
      this.grid[r] = [];
      const row = this.grid[r];
      assert(row !== undefined);
      for (let c = 0; c < cols; c++) {
        row[c] = {
          card: cards[cardIndex++],
          state: "face-down",
          controller: undefined,
          waiters: [],
        };
      }
    }

    this.checkRep();
  }

  /**
   * Check the representation invariant.
   */
  private checkRep(): void {
    assert(this.rows > 0, "rows must be positive");
    assert(this.cols > 0, "cols must be positive");
    assert(
      this.grid.length === this.rows,
      "grid must have correct number of rows"
    );

    const controlledCards = new Map<string, string>(); // position -> playerID

    for (let r = 0; r < this.rows; r++) {
      const row = this.grid[r];
      assert(row !== undefined, `row ${r} must exist`);
      assert(
        row.length === this.cols,
        `row ${r} must have correct number of columns`
      );

      for (let c = 0; c < this.cols; c++) {
        const spot = row[c];
        assert(spot !== undefined, `spot at (${r},${c}) must exist`);

        if (spot.state === "none") {
          assert(
            spot.card === undefined,
            `empty spot at (${r},${c}) should have no card`
          );
          assert(
            spot.controller === undefined,
            `empty spot at (${r},${c}) should have no controller`
          );
        } else if (spot.state === "face-down") {
          assert(
            spot.card !== undefined,
            `face-down spot at (${r},${c}) must have a card`
          );
          assert(
            spot.controller === undefined,
            `face-down spot at (${r},${c}) should have no controller`
          );
        } else {
          // face-up
          assert(
            spot.card !== undefined,
            `face-up spot at (${r},${c}) must have a card`
          );
        }

        if (spot.controller !== undefined) {
          assert(
            spot.state === "face-up",
            `controlled spot at (${r},${c}) must be face-up`
          );
          const key = `${r},${c}`;
          assert(
            !controlledCards.has(key),
            `spot at (${r},${c}) controlled by multiple players`
          );
          controlledCards.set(key, spot.controller);
        }
      }
    }
  }

  /**
   * @returns a string representation of this board showing the grid state
   */
  public toString(): string {
    let result = `Board ${this.rows}x${this.cols}\n`;
    for (let r = 0; r < this.rows; r++) {
      const row = this.grid[r];
      assert(row !== undefined);
      for (let c = 0; c < this.cols; c++) {
        const spot = row[c];
        assert(spot !== undefined);
        if (spot.state === "none") {
          result += "[    ] ";
        } else if (spot.state === "face-down") {
          result += "[????] ";
        } else {
          const ctrl =
            spot.controller !== undefined && spot.controller.length > 0
              ? `*${spot.controller.substring(0, 1)}*`
              : "   ";
          const cardDisplay =
            spot.card !== undefined
              ? spot.card.substring(0, 2).padEnd(2)
              : "??";
          result += `[${cardDisplay}${ctrl}] `;
        }
      }
      result += "\n";
    }
    return result;
  }

  /**
   * Make a new board by parsing a file.
   *
   * PS4 instructions: the specification of this method may not be changed.
   *
   * @param filename path to game board file
   * @returns a new board with the size and cards from the file
   * @throws Error if the file cannot be read or is not a valid game board
   */
  public static async parseFromFile(filename: string): Promise<Board> {
    const content = await fs.promises.readFile(filename, { encoding: "utf-8" });
    const lines = content.split(/\r?\n/);

    // Parse first line: ROWxCOLUMN
    if (lines.length < 1) {
      throw new Error("empty file");
    }

    const dimensionMatch = lines[0]?.match(/^(\d+)x(\d+)$/);
    if (!dimensionMatch) {
      throw new Error("invalid board dimensions format");
    }

    const rows = parseInt(dimensionMatch[1] ?? "0");
    const cols = parseInt(dimensionMatch[2] ?? "0");

    if (rows <= 0 || cols <= 0) {
      throw new Error("board dimensions must be positive");
    }

    const expectedCards = rows * cols;

    // Parse card lines
    const cards: string[] = [];
    for (let i = 1; i <= expectedCards; i++) {
      const line = lines[i];
      if (line === undefined || line === "") {
        throw new Error(`missing card at line ${i + 1}`);
      }

      // Card must be non-empty and contain no whitespace or newlines
      if (!/^[^\s\r\n]+$/.test(line)) {
        throw new Error(`invalid card format at line ${i + 1}`);
      }

      cards.push(line);
    }

    if (cards.length !== expectedCards) {
      throw new Error(
        `expected ${expectedCards} cards but found ${cards.length}`
      );
    }

    return new Board(rows, cols, cards);
  }

  /**
   * Get the current state of the board from a player's perspective.
   *
   * @param playerId the player viewing the board
   * @returns board state string in the format: ROWSxCOLS\n(SPOT\n)+
   *          where SPOT is one of: "none", "down", "up CARD", "my CARD"
   */
  public look(playerId: string): string {
    if (!this.players.has(playerId)) {
      this.players.set(playerId, {
        firstCard: undefined,
        previousCards: [],
      });
    }

    let result = `${this.rows}x${this.cols}\n`;

    for (let r = 0; r < this.rows; r++) {
      const row = this.grid[r];
      assert(row !== undefined);
      for (let c = 0; c < this.cols; c++) {
        const spot = row[c];
        assert(spot !== undefined);

        if (spot.state === "none") {
          result += "none\n";
        } else if (spot.state === "face-down") {
          result += "down\n";
        } else {
          if (spot.controller === playerId) {
            result += `my ${spot.card}\n`;
          } else {
            result += `up ${spot.card}\n`;
          }
        }
      }
    }

    this.checkRep();
    return result;
  }

  /**
   * Attempt to flip a card at the specified position, following game rules.
   * This method is asynchronous and supports waiting when a card is controlled by another player.
   *
   * @param playerId the player attempting the flip
   * @param row row position of the card
   * @param col column position of the card
   * @returns board state string after the flip
   * @throws Error if the flip operation fails according to the rules
   */
  public async flip(
    playerId: string,
    row: number,
    col: number
  ): Promise<string> {
    // Ensure player exists
    if (!this.players.has(playerId)) {
      this.players.set(playerId, {
        firstCard: undefined,
        previousCards: [],
      });
    }

    // Validate coordinates
    if (row < 0 || row >= this.rows || col < 0 || col >= this.cols) {
      throw new Error(`invalid position (${row}, ${col})`);
    }

    const playerState = this.players.get(playerId);
    assert(playerState !== undefined);

    const spot = this.grid[row]?.[col];
    assert(spot !== undefined);

    // Check if this is a first card or second card flip
    if (playerState.firstCard === undefined) {
      // This is a FIRST CARD flip
      return await this.flipFirstCard(playerId, row, col, playerState, spot);
    } else {
      // This is a SECOND CARD flip
      return this.flipSecondCard(playerId, row, col, playerState, spot);
    }
  }

  /**
   * Handle flipping the first card in a pair.
   *
   * @param playerId the player flipping the card
   * @param row row position of the card
   * @param col column position of the card
   * @param playerState the player's current game state
   * @param spot the spot being flipped
   * @returns board state after the flip
   */
  private async flipFirstCard(
    playerId: string,
    row: number,
    col: number,
    playerState: PlayerState,
    spot: Spot
  ): Promise<string> {
    // Rule 3: Before flipping first card, clean up previous play
    this.cleanupPreviousPlay(playerId, playerState);

    // Rule 1-A: No card at this position
    if (spot.state === "none") {
      throw new Error("no card at this position");
    }

    // Rule 1-D: Card is controlled by another player - WAIT
    if (spot.controller !== undefined && spot.controller !== playerId) {
      // Wait for the card to become available
      await this.waitForCard(spot);
      // After waiting, retry the flip
      return await this.flipFirstCard(playerId, row, col, playerState, spot);
    }

    // Rule 1-B: Card is face down - flip it up
    if (spot.state === "face-down") {
      spot.state = "face-up";
      spot.controller = playerId;
      playerState.firstCard = { row, col };
      this.notifyChange();
      this.checkRep();
      return this.look(playerId);
    }

    // Rule 1-C: Card is already face up but not controlled - take control
    if (spot.state === "face-up" && spot.controller === undefined) {
      spot.controller = playerId;
      playerState.firstCard = { row, col };
      this.checkRep();
      return this.look(playerId);
    }

    // Card is already controlled by this player (re-flipping own card)
    if (spot.controller === playerId) {
      playerState.firstCard = { row, col };
      this.checkRep();
      return this.look(playerId);
    }

    throw new Error("unexpected state in flipFirstCard");
  }

  /**
   * Handle flipping the second card in a pair.
   *
   * @param playerId the player flipping the card
   * @param row row position of the card
   * @param col column position of the card
   * @param playerState the player's current game state
   * @param spot the spot being flipped
   * @returns board state after the flip
   */
  private flipSecondCard(
    playerId: string,
    row: number,
    col: number,
    playerState: PlayerState,
    spot: Spot
  ): string {
    assert(playerState.firstCard !== undefined);

    // Rule 2-A: No card at this position
    if (spot.state === "none") {
      // Release control of first card
      this.releaseCard(
        playerState.firstCard.row,
        playerState.firstCard.col,
        playerId
      );
      playerState.previousCards = [playerState.firstCard];
      playerState.firstCard = undefined;
      throw new Error("no card at this position");
    }

    // Rule 2-B: Card is controlled by any player (including self)
    if (spot.controller !== undefined) {
      // Release control of first card
      this.releaseCard(
        playerState.firstCard.row,
        playerState.firstCard.col,
        playerId
      );
      playerState.previousCards = [playerState.firstCard];
      playerState.firstCard = undefined;
      throw new Error("card is controlled by a player");
    }

    // Card is face-down or face-up but not controlled
    // Rule 2-C: Flip face-down card up
    if (spot.state === "face-down") {
      spot.state = "face-up";
      this.notifyChange();
    }

    // Now check if the cards match
    const firstSpot =
      this.grid[playerState.firstCard.row]?.[playerState.firstCard.col];
    assert(firstSpot !== undefined);

    if (firstSpot.card === spot.card) {
      // Rule 2-D: Cards match - keep control of both
      spot.controller = playerId;
      // Store both cards as matched pair for removal on next move
      playerState.previousCards = [playerState.firstCard, { row, col }];
      playerState.firstCard = undefined;

      this.checkRep();
      return this.look(playerId);
    } else {
      // Rule 2-E: Cards don't match - relinquish control
      this.releaseCard(
        playerState.firstCard.row,
        playerState.firstCard.col,
        playerId
      );
      playerState.previousCards = [playerState.firstCard, { row, col }];
      playerState.firstCard = undefined;

      this.checkRep();
      return this.look(playerId);
    }
  }

  /**
   * Clean up from previous play according to Rule 3.
   *
   * @param playerId the player whose previous play is being cleaned up
   * @param playerState the player's current game state
   */
  private cleanupPreviousPlay(
    playerId: string,
    playerState: PlayerState
  ): void {
    if (playerState.previousCards.length === 0) {
      return;
    }

    // Check if previous cards were a match
    if (playerState.previousCards.length === 2) {
      const [first, second] = playerState.previousCards;
      assert(first !== undefined && second !== undefined);

      const firstSpot = this.grid[first.row]?.[first.col];
      const secondSpot = this.grid[second.row]?.[second.col];

      if (
        firstSpot !== undefined &&
        firstSpot.controller === playerId &&
        secondSpot !== undefined &&
        secondSpot.controller === playerId &&
        firstSpot.card === secondSpot.card
      ) {
        // Rule 3-A: Matched pair - remove both cards
        firstSpot.state = "none";
        firstSpot.card = undefined;
        firstSpot.controller = undefined;
        this.notifyWaiters(firstSpot);

        secondSpot.state = "none";
        secondSpot.card = undefined;
        secondSpot.controller = undefined;
        this.notifyWaiters(secondSpot);

        this.notifyChange();
        playerState.previousCards = [];
        return;
      }
    }

    // Rule 3-B: Non-matching cards - turn face down if possible
    let changed = false;
    for (const pos of playerState.previousCards) {
      const spot = this.grid[pos.row]?.[pos.col];
      if (
        spot !== undefined &&
        spot.state === "face-up" &&
        spot.controller === undefined
      ) {
        spot.state = "face-down";
        changed = true;
      }
    }

    if (changed) {
      this.notifyChange();
    }

    playerState.previousCards = [];
  }

  /**
   * Release control of a card (but keep it face up) and notify waiters.
   *
   * @param row row position of the card
   * @param col column position of the card
   * @param playerId the player releasing control
   */
  private releaseCard(row: number, col: number, playerId: string): void {
    const spot = this.grid[row]?.[col];
    if (spot !== undefined && spot.controller === playerId) {
      spot.controller = undefined;
      // Notify all waiting players
      this.notifyWaiters(spot);
    }
  }

  /**
   * Wait for a card to become available (no longer controlled).
   *
   * @param spot the spot to wait for
   * @returns a promise that resolves when the card becomes available
   */
  private async waitForCard(spot: Spot): Promise<void> {
    // If card is already available, return immediately
    if (spot.controller === undefined) {
      return;
    }

    // Otherwise, create a promise and add it to waiters
    const { promise, resolve } = Promise.withResolvers<void>();
    spot.waiters.push(resolve);
    return promise;
  }

  /**
   * Notify all waiters that a card has become available.
   *
   * @param spot the spot whose waiters should be notified
   */
  private notifyWaiters(spot: Spot): void {
    // Notify all waiters
    for (const resolve of spot.waiters) {
      resolve();
    }
    // Clear the waiters array
    spot.waiters = [];
  }

  /**
   * Apply a transformer function to every card on the board.
   * This operation maintains pairwise consistency: if two cards match at the start,
   * they will continue to match during the transformation.
   *
   * @param playerId the player applying the transformation
   * @param f transformer function from card to card (async)
   * @returns board state after transformation
   */
  public async map(
    playerId: string,
    f: (card: string) => Promise<string>
  ): Promise<string> {
    // Ensure player exists
    if (!this.players.has(playerId)) {
      this.players.set(playerId, {
        firstCard: undefined,
        previousCards: [],
      });
    }

    // Build a map of unique cards to their transformations
    // This ensures pairwise consistency - same input always maps to same output
    const transformCache = new Map<string, Promise<string>>();

    // Collect all transformations
    const transformations: Array<{
      row: number;
      col: number;
      originalCard: string;
      transformPromise: Promise<string>;
    }> = [];

    for (let r = 0; r < this.rows; r++) {
      const row = this.grid[r];
      assert(row !== undefined);
      for (let c = 0; c < this.cols; c++) {
        const spot = row[c];
        assert(spot !== undefined);

        if (spot.card !== undefined) {
          // Get or create transformation for this card
          let transformPromise = transformCache.get(spot.card);
          if (transformPromise === undefined) {
            transformPromise = f(spot.card);
            transformCache.set(spot.card, transformPromise);
          }

          transformations.push({
            row: r,
            col: c,
            originalCard: spot.card,
            transformPromise,
          });
        }
      }
    }

    // Wait for all transformations to complete
    await Promise.all(transformations.map((t) => t.transformPromise));

    // Apply all transformations atomically
    for (const { row, col, transformPromise } of transformations) {
      const spot = this.grid[row]?.[col];
      assert(spot !== undefined);

      if (spot.card !== undefined) {
        const newCard = await transformPromise;
        spot.card = newCard;
      }
    }

    // Notify watchers of changes
    this.notifyChange();

    this.checkRep();
    return this.look(playerId);
  }

  /**
   * Watch for changes to the board.
   * Waits until any cards turn face up or face down, are removed from the board,
   * or change from one string to a different string.
   *
   * @param playerId the player watching the board
   * @returns board state after a change occurs
   */
  public async watch(playerId: string): Promise<string> {
    // Ensure player exists
    if (!this.players.has(playerId)) {
      this.players.set(playerId, {
        firstCard: undefined,
        previousCards: [],
      });
    }

    // Wait for a change
    const { promise, resolve } = Promise.withResolvers<void>();
    this.changeWatchers.push(resolve);
    await promise;

    // Return updated board state
    return this.look(playerId);
  }

  /**
   * Notify all watchers that the board has changed.
   */
  private notifyChange(): void {
    // Notify all watchers
    for (const resolve of this.changeWatchers) {
      resolve();
    }
    // Clear the watchers array
    this.changeWatchers.length = 0;
  }
}
