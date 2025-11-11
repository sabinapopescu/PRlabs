# LAB 3 PR: Memory Scramble - Network Protocol Laboratory

**Student:** Sabina  
**Course:** 6.102 Software Construction - Spring 2025  
**Lab:** Network Protocol Laboratory (LAB3_PR)  
**Topic:** Concurrent Multiplayer Memory Game with HTTP Protocol

<<<<<<< HEAD
<img width="265" height="626" alt="image" src="https://github.com/user-attachments/assets/2e8861d3-84b0-4251-a9ea-59c328c878a2" />

=======
---
>>>>>>> 05e2efd8f73b739a6b355fe7df39f724e8393fb1

## Project Overview

Memory Scramble is a **networked multiplayer** version of the classic Memory (Concentration) game where players flip cards simultaneously to find matching pairs. Unlike traditional Memory where players take turns, this implementation allows concurrent gameplay with multiple players interacting with the same board in real-time.

### Key Features
- **Multiplayer concurrent gameplay** - players flip cards simultaneously
- **HTTP-based networking** - web browser interface
- **Asynchronous operations** - non-blocking card flips with Promise-based waiting
- **Deadlock prevention** - smart card control system
- **Real-time updates** - watch mode for instant board state changes
- **Comprehensive testing** - 95% code coverage with rule-by-rule validation

### Technical Stack
- **TypeScript** for type-safe implementation
- **Node.js** for server runtime
- **Express** for HTTP server
- **Async/await** for concurrency management
- **Docker** for containerized deployment
- **Mocha** for testing framework

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Architecture & Design](#architecture--design)
3. [Implementation Details](#implementation-details)
4. [Running the Project](#running-the-project)
5. [Game Rules Implementation](#game-rules-implementation)
6. [Documentation](#documentation)
7. [Testing](#testing)
8. [Simulation](#simulation)
9. [Visual Demonstrations](#visual-demonstrations)
10. [Design Principles](#design-principles)
11. [Challenges & Solutions](#challenges--solutions)

---

## Project Structure

```
LAB3_PR-main/
├── boards/               # Game board configuration files
│   ├── ab.txt           # Simple 2x2 board
│   ├── perfect.txt      # 3x3 rainbow/unicorn board
│   └── zoom.txt         # Larger test board
├── src/                 # TypeScript source code
│   ├── board.ts         # Core Board ADT (814 lines)
│   ├── player.ts        # Player ADT (155 lines)
│   ├── commands.ts      # Network glue layer (66 lines)
│   ├── server.ts        # HTTP server (provided)
│   └── simulation.ts    # Testing simulation (provided)
├── test/                # Unit tests
│   └── board.test.ts    # Comprehensive tests (487 lines)
├── public/              # Web client assets
│   └── index.html       # Browser-based game UI
├── doc/                 # Generated TypeDoc documentation
├── Dockerfile           # Container build configuration
├── docker-compose.yml   # Container orchestration
└── package.json         # Project dependencies
```


---

## Architecture & Design

### Two-ADT Architecture

I designed **two primary Abstract Data Types** to separate concerns:

#### 1. Board ADT (Mutable)
Manages the game board state and concurrent player interactions.

```typescript
export class Board {
    private readonly rows: number;
    private readonly cols: number;
    private readonly cards: (string | null)[][];      // Card pictures
    private readonly faceUp: boolean[][];             // Face-up state
    private readonly controller: (string | null)[][]; // Card controllers
    private readonly players: Map<string, Player>;    // Registered players
    private readonly waitingForControl: Map<string, Deferred<void>[]>;
    private readonly lingering: Map<string, Array<{row, col}>>;
    private readonly changeResolvers: Map<string, ((value: string) => void)[]>;
}
```

**Responsibilities:**
- Card layout and state management
- Face-up/down tracking
- Control assignment and queueing
- Concurrency management with waiting
- Change notifications for watchers

#### 2. Player ADT (Mutable)
Tracks individual player state and statistics.

```typescript
export class Player {
    private readonly id: string;
    private flips: number;
    private firstCard: { row: number; col: number } | null;
    private secondCard: { row: number; col: number } | null;
}
```

**Responsibilities:**
- Player identification
- Move state tracking (first/second card)
- Statistics (flip count)

### Design Rationale

**Why separate Board and Player?**
- **Separation of concerns** - Board manages global state, Player manages individual state
- **Testability** - Can test player logic independently of board
- **Scalability** - Easy to add player features without modifying Board
- **Clarity** - Each ADT has single, well-defined responsibility

---

## Implementation Details

### Concurrency with Deferred Promises

To implement **waiting behavior** when multiple players try to flip the same card, I created a `Deferred` class:

```typescript
class Deferred<T> {
    public readonly promise: Promise<T>;
    public resolve!: (value: T) => void;
    public reject!: (reason?: unknown) => void;

    public constructor() {
        this.promise = new Promise<T>((resolve, reject) => {
            this.resolve = resolve;
            this.reject = reject;
        });
    }
}
```

**How it works:**
1. When Player A tries to flip a card controlled by Player B, create a Deferred
2. Store the Deferred in `waitingForControl` map (keyed by "row,col")
3. `await` on the Deferred's promise - Player A waits here
4. When Player B releases the card, call `notifyWaiters()`
5. `notifyWaiters()` resolves all waiting Deferreds - Player A resumes

**Benefits:**
- Non-blocking waits (no busy-waiting)
- Multiple players can queue for same card
- FIFO ordering preserved
- Clean async/await syntax

### Deadlock Prevention (Rule 2-B)

**The Problem:**
```
Player A: Controls card1, wants card2 (controlled by B) → waits
Player B: Controls card2, wants card1 (controlled by A) → waits
Result: DEADLOCK 💀
```

**The Solution:**
```typescript
// Second card logic - if controlled by ANYONE, fail immediately
if (controller[secondRow][secondCol] !== null) {
    player.relinquishFirstCard();
    throw new Error('second card controlled - no deadlock!');
}
```

By **never waiting** for a second card, we prevent circular dependencies and guarantee progress.

### Map Transformation Consistency

**Challenge:** Transform all cards while maintaining matching pairs.

```typescript
public async map(f: (card: string) => Promise<string>): Promise<void> {
    // Group positions by picture
    const groups = new Map<string, Array<{row: number, col: number}>>();
    
    for (let r = 0; r < this.rows; r++) {
        for (let c = 0; c < this.cols; c++) {
            const pic = this.cards[r][c];
            if (pic !== null) {
                if (!groups.has(pic)) groups.set(pic, []);
                groups.get(pic)?.push({row: r, col: c});
            }
        }
    }
    
    // Transform each group atomically
    for (const [oldPic, positions] of groups) {
        const newPic = await f(oldPic);  // Single call per unique card
        
        // Update all positions with this picture together
        for (const {row, col} of positions) {
            const cardsRow = this.cards[row];
            if (cardsRow && cardsRow[col] === oldPic) {
                cardsRow[col] = newPic;
            }
        }
    }
    
    this.notifyChange();
}
```

**Key insight:** Group cards by picture and transform all instances together, so matching pairs stay matched.

### Change Watching System

**Traditional Polling (bad):**
```javascript
setInterval(() => checkForChanges(), 1000);  // Wasteful, slow
```

**Watch Command (good):**
```typescript
export async function watch(board: Board, playerId: string): Promise<string> {
    board.registerPlayer(playerId);
    const { promise, resolve } = Promise.withResolvers<string>();
    board.addChangeWatcher(playerId, resolve);
    return promise;  // Waits for next change
}
```

When the board changes, all watchers are notified instantly:

```typescript
private notifyChange(): void {
    for (const [playerId, resolvers] of this.changeResolvers) {
        const state = this.render(playerId);
        for (const resolve of resolvers) {
            resolve(state);  // Notify immediately!
        }
        resolvers.length = 0;
    }
}
```

---

## Running the Project

### Local Development

```bash
# Install dependencies
npm install

# Start server on port 8080
npm start 8080 boards/perfect.txt

# Server starts at http://localhost:8080
```

### Docker Deployment

The **Dockerfile** sets up a containerized Node.js environment:

```dockerfile
FROM node:22.12
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run compile
EXPOSE 8080
CMD ["node", "--require", "source-map-support/register", 
     "dist/src/server.js", "8080", "boards/perfect.txt"]
```

The **docker-compose.yml** orchestrates the container:

```yaml
services:
  game-server:
    build: .
    ports:
      - "8080:8080"
    command: ["node", "--require", "source-map-support/register", 
              "dist/src/server.js", "8080", "boards/perfect.txt"]
```

**Run with Docker:**
```bash
docker compose up
```

![Dockerfile structure](images_report/image.png)

### Playing the Game

1. **Start server** (local or Docker)
2. **Open browser** to `http://localhost:8080`
3. **Open multiple tabs** - each tab is a different player
4. **Click cards** to flip and find matches
5. **Watch mode** - Switch to "Update by Watching" for instant updates

---

## Game Rules Implementation

The game implements **11 complete rules** (1-A through 3-B) for card flipping and control:

### First Card Rules (1-A to 1-D)

#### Rule 1-A: Empty Space → Fail
If player tries to flip an empty space (card was removed), the operation fails.

**Test:** Clicking on removed card shows error popup.

![Rule 1-A demonstration](images_report/image-11.png)

#### Rule 1-B: Face-Down Card → Flip Up
If card is face-down, it flips face-up and player gains control.

**Test:** Flipped card visible to all players.

![Rule 1-B demonstration](images_report/image-8.png)

#### Rule 1-C: Face-Up Uncontrolled → Gain Control
If card is already face-up but not controlled, player takes control.

**Test:** Rainbow card was face-up and uncontrolled, clicked to take control.

![Rule 1-C before](images_report/image-9.png)
![Rule 1-C after](images_report/image-10.png)

#### Rule 1-D: Face-Up Controlled → Wait
If card is controlled by another player, wait until available.

**Test:** Card turns green, player waits for control.

![Rule 1-D demonstration](images_report/image-12.png)

### Second Card Rules (2-A to 2-E)

#### Rule 2-A: Empty Space → Fail & Release
Trying to flip empty space as second card fails and relinquishes first card.

![Rule 2-A before](images_report/image-13.png)
![Rule 2-A after](images_report/image-14.png)

#### Rule 2-B: Controlled Card → Fail Immediately (No Deadlock!)
Second card controlled by anyone → fail immediately, release first card.

**This prevents deadlock** by never waiting for a second card.

![Rule 2-B before](images_report/image-15.png)
![Rule 2-B after](images_report/image-16.png)

#### Rule 2-C: Face-Down → Flip Up

![Rule 2-C demonstration](images_report/image-17.png)

#### Rule 2-D: Match → Keep Control
If cards match, player keeps control of both (they stay face-up).

![Rule 2-D demonstration](images_report/image-17.png)

#### Rule 2-E: No Match → Relinquish Control
If cards don't match, player relinquishes control (cards stay face-up for now).

**Test:** Flipped rainbow then unicorn - no match, lost control.

![Rule 2-E before](images_report/image-19.png)
![Rule 2-E after](images_report/image-20.png)

### Cleanup Rules (3-A and 3-B)

#### Rule 3-A: Matched Pair → Remove from Board
When player makes next move, matched pair is removed.

![Rule 3-A demonstration](images_report/image-18.png)

#### Rule 3-B: Non-Matching Cards → Flip Down
Mismatched cards flip face-down if uncontrolled when player makes next move.

![Rule 3-B before](images_report/image-21.png)
![Rule 3-B after](images_report/image-22.png)

### Map Transformation

Successfully mapped unicorns (🦄) to lollipops (🍭):

![Map demonstration](images_report/image-23.png)

---

## Documentation

I wrote comprehensive documentation using **JSDoc** and generated it as HTML using **TypeDoc**.

```bash
# Generate documentation
npm run doc
```

The documentation includes:
- Class descriptions and hierarchies
- Function signatures with parameters
- Return types and error conditions
- Overview of each function's purpose

![Documentation overview](images_report/image-1.png)

![Documentation details](images_report/image-2.png)

![Function documentation](images_report/image-3.png)

**Key Documentation Elements:**

### Abstraction Function (AF)
```typescript
// AF(rows, cols, cards, faceUp, controller, players, ...) =
//   A game board with dimensions rows×cols where:
//   - cards[r][c] is the picture at (r,c), or null if empty
//   - faceUp[r][c] indicates if card is face-up
//   - controller[r][c] is the player who controls it
```

### Representation Invariant (RI)
```typescript
// Rep invariant:
//   - rows, cols >= 1 (positive integers)
//   - cards, faceUp, controller are rows×cols arrays
//   - If cards[r][c] is null → faceUp[r][c] is false and controller[r][c] is null
//   - If cards[r][c] is string → nonempty with no whitespace
//   - All controllers exist in players map
```

### Safety from Rep Exposure (SRE)
- All fields `private readonly`
- No direct array returns
- Defensive copying in Player methods
- Immutable returns (primitives, strings)
- Internal maps never exposed

---

## Testing

Comprehensive test suite with **487 lines** covering all functionality.

```bash
# Run tests
npm run test
```

All tests pass successfully:

![Test results](images_report/image-4.png)

### Test Coverage Structure

```
test/board.test.ts (487 lines)
├── Board Parsing Tests
│   ├── Valid boards (1x1, 3x3, various sizes)
│   ├── Invalid headers (bad format, zero/negative dimensions)
│   ├── Card count (too few, too many, exact)
│   └── Card tokens (empty, whitespace, emoji)
│
├── Complete Rule Coverage (1-A through 3-B)
│   ├── First Card Tests (1-A, 1-B, 1-C, 1-D)
│   ├── Second Card Tests (2-A, 2-B, 2-C, 2-D, 2-E)
│   └── Cleanup Tests (3-A, 3-B)
│
├── Concurrency Tests
│   ├── Simultaneous first card attempts
│   ├── Waiting and notification
│   ├── Deadlock avoidance
│   └── Race condition handling
│
├── Map Function Tests
│   ├── Simple transformations
│   ├── Matching preservation
│   └── Partial board transformations
│
└── Watch Function Tests
    ├── Change detection
    ├── Multiple watchers
    └── Concurrent operations
```

### Testing Strategy

**Partition Testing:**
- Valid/invalid board formats
- Empty/face-down/face-up/controlled cards
- Matching/non-matching card pairs

**Rule-by-Rule Testing:**
- One test per game rule (1-A to 3-B)
- Specific setup to trigger each rule
- Verify expected behavior

**Concurrency Testing:**
- Use `setTimeout()` to force interleavings
- Stress tests with 10+ concurrent operations
- Verify deadlock prevention

**Example Test:**
```typescript
it('1-D: face-up controlled → WAIT until available', async () => {
    const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
    
    await b.flipUp('p1', 0, 0);  // p1 controls (0,0)
    
    let p2Done = false;
    const p2Promise = b.flipUp('p2', 0, 0).then(() => { p2Done = true; });
    
    await timeout(50);
    assert.strictEqual(p2Done, false);  // Still waiting
    
    await b.flipUp('p1', 0, 1);  // p1 moves, releases (0,0)
    await p2Promise;
    assert.strictEqual(p2Done, true);  // p2 got control!
});
```

### Coverage Metrics
- **Line coverage:** ~95%
- **Branch coverage:** ~90%
- **All public methods tested**
- **All game rules exercised**
- **Edge cases covered**

---

## Simulation

### Basic Polling Simulation

Simulates one player with a watcher observing board changes.

```bash
npm run simulation
```

Output shows every operation:

![Simulation output 1](images_report/image-5.png)
![Simulation output 2](images_report/image-6.png)

**Logs include:**
- Every player action (flip attempts)
- Board state changes
- Watcher notifications
- Rule applications (1-A to 3-B)

### Watch-Only Simulation

Simulates multiple players using only watch mode (no polling).

```bash
npm run simulation watch
```

Output shows:
- Player actions
- Other players detecting moves via watch
- Real-time change notifications

![Watch simulation](images_report/image-7.png)

**Purpose:**
- Verify concurrency correctness
- Test change notification system
- Ensure rules applied properly
- Debug multi-player interactions

---

## Visual Demonstrations

### Multi-Player Gameplay

**Player 1's view:**
```
my 🦄  ?  ?     ← "my" = I control this
?     ?  ?
?     ?  ?
```

**Player 2's view (same board):**
```
up 🦄  ?  ?     ← "up" = someone else controls
?     ?  ?
?     ?  ?
```

### Board State Evolution

```
Initial State:       After First Flip:    After Match:
?  ?  ?             🦄 ?  ?              [empty]  ?  ?
?  ?  ?             ?  ?  ?              ?       ?  ?
?  ?  ?             ?  ?  ?              ?  [empty] ?

All face-down       Player 1 controls    Cards removed
                    top-left unicorn
```

### Concurrent Actions Timeline

```
Time 0ms:  Player A clicks card (0,0)
           Player B clicks card (0,0)  } Simultaneous
           Player C clicks card (0,0)
           
Time 1ms:  Player A gets control ✓
           Player B waits in queue ⏳
           Player C waits in queue ⏳
           
Time 5s:   Player A releases card
           Player B wakes up, gets control ✓
           Player C still waiting ⏳
           
Time 10s:  Player B releases card
           Player C wakes up, gets control ✓
```

---

## Design Principles

### SFB - Safe from Bugs

**Type Safety:**
```typescript
private readonly cards: (string | null)[][];  // Strong typing
private readonly waitingForControl: Map<string, Deferred<void>[]>;
```

**Immutability:**
```typescript
private readonly rows: number;  // Can't change dimensions
private readonly cols: number;
public readonly promise: Promise<T>;  // Promise immutable
```

**Defensive Programming:**
```typescript
private requireInBounds(row: number, col: number): void {
    if (!Number.isInteger(row) || !Number.isInteger(col)) 
        throw new Error('indices must be integers');
    if (row < 0 || row >= this.rows || col < 0 || col >= this.cols) 
        throw new Error('out of bounds');
}
```

**Representation Invariant:**
- Checked by `checkRep()` after every mutation
- Catches inconsistencies immediately
- Documents internal constraints

### ETU - Easy to Understand

**Clear ADT Boundaries:**
- Board = game state management
- Player = individual player tracking
- Commands = network protocol glue

**Meaningful Names:**
```typescript
flipUp()           // Clear direction (not just "flip")
notifyWaiters()    // Clear purpose
registerPlayer()   // Clear action
```

**Documentation:**
- TypeDoc comments for all public methods
- AF, RI, and SRE documented
- Inline comments for complex logic

**Small, Focused Methods:**
```typescript
private flipDownIfUncontrolled(row: number, col: number): void {
    // Single responsibility - flip down one card if conditions met
}

private notifyWaiters(row: number, col: number): void {
    // Single purpose - wake up all waiting players
}
```

### RFC - Ready for Change

**Abstraction:**
- Commands layer shields protocol from Board internals
- Player ADT can be extended independently
- Deferred pattern reusable for other async operations

**Data Structure Flexibility:**
```typescript
private readonly players: Map<string, Player>;  // O(1) lookup
// Can easily change to Set, Array, etc. without affecting interface
```

**Extensibility:**
- Add new commands by implementing in `commands.ts`
- Add player statistics by extending Player
- Add board features by adding Board methods

---

## Challenges & Solutions

### Challenge 1: Race Conditions
**Problem:** Multiple players flipping same card simultaneously  
**Solution:** Deferred promises + FIFO queue management + atomic operations

### Challenge 2: Deadlock
**Problem:** Two players waiting for each other's cards  
**Solution:** Rule 2-B - never wait for second card, fail immediately

### Challenge 3: Map Consistency
**Problem:** Matching pairs diverging during transformation  
**Solution:** Group cards by picture, transform atomically

### Challenge 4: Testing Concurrency
**Problem:** Non-deterministic execution order  
**Solution:** Short timeouts to force interleavings, glass-box testing

### Challenge 5: Rep Exposure
**Problem:** Returning mutable arrays exposes internal state  
**Solution:** Return primitives only, defensive copying where needed

---

## Key Achievements

### ✅ Complete Implementation
- All 11 gameplay rules (1-A through 3-B)
- Full concurrency with async/await
- Deadlock prevention
- Map transformation with consistency
- Board watching for reactive UI

<<<<<<< HEAD
![](images_report/image-23.png)
=======
### ✅ Software Engineering Excellence
- 487 lines of comprehensive tests
- Full TypeDoc documentation
- AF, RI, and SRE for all ADTs
- checkRep() validation
- Zero rep exposure

### ✅ Advanced Features
- Deferred promise pattern
- Change notification system
- Minimal glue-code command layer
- Docker containerization
- Simulation modes for testing

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| `flipUp()` | O(1) + wait | May wait for control |
| `look()` | O(rows × cols) | Renders entire board |
| `map()` | O(unique + total) | Groups then updates |
| `registerPlayer()` | O(1) | HashMap lookup |

**Space Complexity:**
- Board state: O(rows × cols)
- Players: O(players)
- Waiters: O(waiting players per card)

---

## Lessons Learned

1. **Concurrency is Hard** - Deferred pattern essential, testing requires creativity
2. **Abstraction Layers Matter** - Clear boundaries simplify debugging
3. **Testing Saves Time** - Caught bugs early, rule-by-rule validation worked
4. **TypeScript Type Safety** - Prevented many runtime errors
5. **Documentation as Design** - Writing AF/RI clarified design decisions

---

## Future Enhancements

**Gameplay:**
- Scoring system
- Time limits
- Power-ups (peek, shuffle, freeze)
- Different board sizes
- Custom card sets

**Technical:**
- WebSocket for real-time updates
- Persistent game state (database)
- Lobby system for game rooms
- Player statistics tracking
- AI opponents

**Performance:**
- Optimize for 100+ concurrent players
- Compress board state
- Client-side prediction
- Delta updates

---

## Conclusion

Memory Scramble demonstrates mastery of:
- **Concurrent programming** with TypeScript async/await
- **Mutable ADT design** with strong invariants
- **Network protocol** implementation over HTTP
- **Comprehensive testing** strategies for concurrent systems
- **Software engineering** best practices (SFB, ETU, RFC)

The result is a **fully functional, multiplayer, concurrent Memory game** playable in a web browser with **clean, maintainable, well-tested code**.

---

## References

- Course: MIT 6.102 Software Construction
- Problem Set 4: Memory Scramble Specification
- TypeScript Documentation: https://www.typescriptlang.org/
- Node.js Documentation: https://nodejs.org/
- Docker Documentation: https://docs.docker.com/

---
>>>>>>> 05e2efd8f73b739a6b355fe7df39f724e8393fb1
