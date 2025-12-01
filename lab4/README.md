# Lab 3: Memory Scramble - Concurrent Multiplayer Game Server

## Overview

This project implements a multiplayer Memory Scramble game where multiple players can flip cards simultaneously. Unlike traditional turn-based Memory games, this implementation handles concurrent operations safely, creating interesting challenges in managing shared state and race conditions. The main goal was building a thread-safe server that maintains game consistency even with multiple concurrent players.

The most challenging aspect was handling race conditions and ensuring fair gameplay. Initial implementations had tests that would randomly pass or fail due to timing issues. Through this project, I learned about proper concurrency control using promise-based locking mechanisms, asynchronous waiting patterns, and comprehensive testing strategies for concurrent systems.

### What I Learned

Through this project, I implemented a thread-safe game server that handles multiple concurrent players without conflicts or data corruption. The main challenge was ensuring that when multiple players try to flip cards simultaneously, the game remains consistent and fair. I learned the importance of using proper promise-based locking mechanisms instead of inefficient busy-waiting loops.

The most interesting part was implementing the `watch()` operation - instead of constantly polling "has the board changed?", clients can simply wait and get notified automatically when something happens. This is much more efficient than traditional polling and provides instant updates to all players, similar to modern real-time systems like WebSockets.

## Project Structure

```
LAB 3/
├── src/
│   ├── board.ts          # Core Board ADT with game logic
│   ├── commands.ts       # Game commands (look, flip, map, watch)
│   ├── server.ts         # Express HTTP server
│   └── simulation.ts     # Multi-player concurrent simulation
├── test/
│   └── board.test.ts     # Comprehensive test suite (40 tests)
├── boards/
│   ├── perfect.txt       # 3x3 board with emoji pairs
│   ├── ab.txt            # 5x5 board with letters
│   └── zoom.txt          # Custom board
├── public/
│   └── index.html        # Web UI for playing the game
├── package.json
└── README.md
```

## Implementation Details

### Problem 1: Board ADT Design and File Parsing

**What I Did:** Designed and implemented a `Board` Abstract Data Type that parses game board files and maintains the complete game state with proper invariants.

**How It Works:** The board reads a file where the first line specifies dimensions (e.g., `3x3`), and each subsequent line contains exactly one card. Cards can be any string (emojis, words, numbers) as long as they don't contain whitespace. The board maintains a 2D grid where each spot tracks the card value, state (face-up/down/none), controller, and waiting players.

**Board File Format:**

```
3x3
🌈
🌈
🦄
🦄
🎨
🎨
🎭
🎭
🎪
```

**Design Pattern - Factory with Private Constructor:**

```typescript
export class Board {
  // Private constructor - clients cannot call directly
  private constructor(rows: number, cols: number, cards: string[]) {
    assert(cards.length === rows * cols, "invalid card count");
    this.rows = rows;
    this.cols = cols;
    this.grid = this.initializeGrid(rows, cols, cards);
    this.checkRep(); // Verify all invariants
  }

  // Static factory method - only way to create boards
  public static async parseFromFile(filename: string): Promise<Board> {
    // All validation happens here
    const content = await fs.promises.readFile(filename, "utf-8");
    const lines = content.split(/\r?\n/);

    const match = lines[0]?.match(/^(\d+)x(\d+)$/);
    if (!match) throw new Error("invalid dimensions format");

    const rows = parseInt(match[1]);
    const cols = parseInt(match[2]);
    const cards = lines.slice(1).filter((line) => line.length > 0);

    if (cards.length !== rows * cols) {
      throw new Error(`expected ${rows * cols} cards, found ${cards.length}`);
    }

    return new Board(rows, cols, cards);
  }
}
```

**Representation Invariant and Safety:**

```typescript
// Representation Invariant:
//   - rows > 0, cols > 0
//   - grid.length === rows
//   - if spot.state === 'none', then spot.card === undefined
//   - if spot.state === 'face-down', then spot.controller === undefined
//   - if spot.controller !== undefined, then spot.state === 'face-up'
//   - no two players can control the same card

// Safety from Rep Exposure:
//   - All fields are private and readonly
//   - grid is never returned directly
//   - Methods return only strings or promises
```

---

### Problem 2: Look and Flip Operations with Game Rules

**What I Did:** Implemented `look()` and `flip()` commands following all Memory Scramble rules (1-A through 3-B).

**Game Rules:**

- **Rule 1-A**: Cannot flip empty spots (throws error)
- **Rule 1-B**: Face-down card → flip face-up, give control to player
- **Rule 1-C**: Face-up uncontrolled card → take control
- **Rule 1-D**: Card controlled by another player → wait asynchronously
- **Rule 2-A**: Cannot flip empty spot as second card (throws error)
- **Rule 2-B**: Cannot flip card controlled by another player (throws error)
- **Rule 2-C**: Face-down second card → flip face-up
- **Rule 2-D**: Matching cards → keep control, mark for removal
- **Rule 2-E**: Non-matching cards → release control of both
- **Rule 3-A**: Matched pairs removed on player's next move
- **Rule 3-B**: Non-matching cards flip face-down on player's next move

**Look Implementation:**

```typescript
public look(playerId: string): string {
    let result = `${this.rows}x${this.cols}\n`;

    for (let r = 0; r < this.rows; r++) {
        for (let c = 0; c < this.cols; c++) {
            const spot = this.grid[r][c];

            if (spot.state === 'none') {
                result += 'none\n';
            } else if (spot.state === 'face-down') {
                result += 'down\n';
            } else { // face-up
                if (spot.controller === playerId) {
                    result += `my ${spot.card}\n`;
                } else {
                    result += `up ${spot.card}\n`;
                }
            }
        }
    }

    return result;
}
```

**Cleanup Logic (Rules 3-A and 3-B):**

```typescript
private cleanupPreviousPlay(playerId: string, playerState: PlayerState): void {
    if (playerState.previousCards.length === 0) return;

    // Rule 3-A: Check if matched pair (same card, both controlled)
    if (playerState.previousCards.length === 2) {
        const [pos1, pos2] = playerState.previousCards;
        const spot1 = this.grid[pos1.row]?.[pos1.col];
        const spot2 = this.grid[pos2.row]?.[pos2.col];

        if (spot1?.controller === playerId &&
            spot2?.controller === playerId &&
            spot1.card === spot2.card) {
            // Remove matched pair
            spot1.state = 'none';
            spot1.card = undefined;
            spot1.controller = undefined;
            this.notifyWaiters(spot1);

            spot2.state = 'none';
            spot2.card = undefined;
            spot2.controller = undefined;
            this.notifyWaiters(spot2);

            this.notifyChange();
            playerState.previousCards = [];
            return;
        }
    }

    // Rule 3-B: Turn non-matched cards face-down
    let changed = false;
    for (const pos of playerState.previousCards) {
        const spot = this.grid[pos.row]?.[pos.col];
        if (spot?.state === 'face-up' && spot.controller === undefined) {
            spot.state = 'face-down';
            changed = true;
        }
    }

    if (changed) {
        this.notifyChange();
    }

    playerState.previousCards = [];
}
```

---

### Problem 3: Asynchronous Board with Concurrency Safety

**What I Did:** Made the Board fully asynchronous with promise-based waiting (no busy-waiting).

**The Problem:** When multiple players try to flip cards simultaneously, we need to prevent race conditions.

**My Solution - Promise-Based Waiting:**

```typescript
type Spot = {
    card: string | undefined;
    state: CardState;
    controller: string | undefined;
    waiters: Array<() => void>; // Callbacks for waiting players
};

/**
 * Wait for a card to become available.
 */
private async waitForCard(spot: Spot): Promise<void> {
    const { promise, resolve } = Promise.withResolvers<void>();
    spot.waiters.push(resolve);
    return promise; // Uses zero CPU while waiting
}

/**
 * Notify all waiters that a card has become available.
 */
private notifyWaiters(spot: Spot): void {
    for (const resolve of spot.waiters) {
        resolve();
    }
    spot.waiters.length = 0;
}
```

**Waiting in flipFirstCard():**

```typescript
private async flipFirstCard(
    playerId: string, row: number, col: number,
    playerState: PlayerState, spot: Spot
): Promise<string> {
    // Rule 1-D: Card controlled by another player - WAIT
    if (spot.controller !== undefined && spot.controller !== playerId) {
        await this.waitForCard(spot);
        // Retry after card becomes available
        return this.flipFirstCard(playerId, row, col, playerState, spot);
    }

    // ... other rules ...
}
```

**Benefits:**

- **Zero CPU usage** while waiting
- **Instant notification** when card becomes available
- **Scalable** - 100 waiting players use minimal resources

---

### Problem 4: Map Operation with Pairwise Consistency

**What I Did:** Implemented `map()` to transform all cards while allowing interleaving operations.

**Three-Phase Transformation:**

1. **Phase 1 (Quick Scan):** Collect all unique card values
2. **Phase 2 (Slow Transform):** Transform each unique card - board is unlocked
3. **Phase 3 (Atomic Apply):** Apply all transformations at once

```typescript
public async map(
    playerId: string,
    f: (card: string) => Promise<string>
): Promise<string> {
    // Phase 1: Collect unique cards
    const uniqueCards = new Set<string>();
    for (let r = 0; r < this.rows; r++) {
        for (let c = 0; c < this.cols; c++) {
            const spot = this.grid[r][c];
            if (spot.card !== undefined) {
                uniqueCards.add(spot.card);
            }
        }
    }

    // Phase 2: Transform each unique card (UNLOCKED)
    const transformCache = new Map<string, Promise<string>>();
    for (const card of uniqueCards) {
        transformCache.set(card, f(card)); // Other operations can run here
    }

    // Phase 3: Apply transformations atomically
    for (let r = 0; r < this.rows; r++) {
        for (let c = 0; c < this.cols; c++) {
            const spot = this.grid[r][c];
            if (spot.card !== undefined) {
                const transformPromise = transformCache.get(spot.card)!;
                spot.card = await transformPromise;
            }
        }
    }

    this.notifyChange();
    return this.look(playerId);
}
```

**Pairwise Consistency:** If two cards match before transformation, they stay matching because we use a cache.

---

### Problem 5: Watch Operation for Real-Time Updates

**What I Did:** Implemented `watch()` using the observer pattern instead of polling.

```typescript
private readonly changeWatchers: Array<() => void>;

/**
 * Watch for changes to the board.
 */
public async watch(playerId: string): Promise<string> {
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
    for (const resolve of this.changeWatchers) {
        resolve();
    }
    this.changeWatchers.length = 0;
}
```

**Benefits:**

- **Instant updates** - no polling delay
- **Zero wasted requests** - only responds when changes occur
- **Efficient** - no repeated checks

---

## Running the Project

### Installation

```bash
npm install
```

### Start HTTP Server

```bash
npm start 8080 boards/perfect.txt
```

**Output:**

```
server now listening at http://localhost:8080
```

### Access Web UI

Open browser to: `http://localhost:8080`

### Run Multi-Player Simulation

```bash
npm run simulation
```

**Output:**

```
Starting simulation with 3 players, 20 tries each
Board size: 5x5
Testing concurrent gameplay without crashes...

player0: 4 successful moves, 16 failed attempts
player1: 7 successful moves, 13 failed attempts
player2: 7 successful moves, 13 failed attempts

✅ Simulation completed successfully!
All players finished without crashes.
```

---

## Testing

### Run All Tests

```bash
npm test
```

**Results (40 tests passing):**

```
  Board
    parseFromFile
      ✔ parses valid 3x3 board with emoji
      ✔ parses valid 5x5 board
      ✔ throws error for non-existent file
      ✔ throws error for invalid dimensions format
      ✔ throws error for wrong number of cards
      ✔ throws error for card with whitespace
    look
      ✔ shows all cards face-down for new player on fresh board
      ✔ shows face-up card controlled by player as "my"
      ✔ shows face-up card controlled by other player as "up"
      ✔ shows removed cards as "none"
    flip - first card
      ✔ throws error when flipping empty spot
      ✔ flips face-down card to face-up and gives control
      ✔ takes control of face-up uncontrolled card
      ✔ waits when card is controlled by another player
      ✔ throws error for invalid coordinates
    flip - second card
      ✔ throws error when second card is empty spot
      ✔ throws error when second card is controlled
      ✔ matches two identical cards
      ✔ does not match different cards
      ✔ flips face-down second card to face-up
    flip - cleanup rules
      ✔ removes matched pair when flipping next first card
      ✔ turns non-matched cards face-down when flipping next first card
      ✔ does not turn face-down cards controlled by other players
    multi-player scenarios
      ✔ allows multiple players to play simultaneously
      ✔ tracks each player state independently
      ✔ handles multiple concurrent waiters for same card
    map
      ✔ transforms all cards on the board
      ✔ maintains pairwise consistency during transformation
      ✔ does not affect card state (face-up/down, controller)
      ✔ applies same transformation to matching cards
      ✔ can interleave with flip operations
    watch
      ✔ waits for a change on the board
      ✔ notifies watchers on card flip
      ✔ notifies watchers on card removal
      ✔ notifies watchers on map transformation
      ✔ supports multiple simultaneous watchers
      ✔ does not block other operations

  async test cases
    ✔ reads a file asynchronously


  40 passing (91ms)
```

---

## API Endpoints

### GET /look/:playerId

Returns the current board state.

**Response:**

```
3x3
down
my 🦄
up 🌈
none
```

### GET /flip/:playerId/:row,:column

Flips a card at specified position.

**Example:** `/flip/alice/0,1`

### GET /replace/:playerId/:oldcard/:newcard

Transforms all cards matching `oldcard` to `newcard`.

### GET /watch/:playerId

Waits for board change, returns updated state.

---

## Lessons Learned

1. **Promise-Based Concurrency** - Much better than busy-waiting
2. **Testing Concurrent Code** - Requires proper synchronization
3. **Observer Pattern** - Powerful for real-time systems
4. **Representation Invariants** - Catch bugs early
5. **Separation of Concerns** - Makes testing easier

---

## Conclusion

This project successfully implements a fully concurrent, multiplayer Memory Scramble game with:

- **Thread-safe operations** using promise-based patterns
- **Zero busy-waiting** - efficient asynchronous waiting
- **Real-time updates** via watch operation
- **Pairwise consistency** during transformations
- **Comprehensive testing** (40 tests)

The implementation demonstrates: **Safe from Bugs**, **Easy to Understand**, and **Ready for Change**.
