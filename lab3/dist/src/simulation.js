import { Board } from './board.js';
const TIMESTAMP_START = 11;
const TIMESTAMP_END = 23;
const SEPARATOR_WIDTH = 60;
const CELL_PADDING = 20;
const BOARD_CHECK_INTERVAL = 5;
const BOARD_CHECK_OFFSET = 4;
const MAX_WATCH_TIMEOUT_MS = 2000;
/**
 * Execute a simulation of Memory Scramble with automated players.
 * This demonstrates the game mechanics with players making random moves.
 * Includes a watcher that monitors board changes in real-time.
 *
 * @throws Error if the board file cannot be loaded or parsed
 */
async function simulationMain() {
    const filename = 'boards/ab.txt';
    const board = await Board.parseFromFile(filename);
    const players = 4; // simulate multi-player
    const triesPerPlayer = 100; // each player will attempt this many flips
    const maxDelayMs = 5; // tiny delays to force interleavings
    // Utility to yield control briefly 
    const timeout = (ms) => new Promise(res => setTimeout(res, ms));
    // register players
    const ids = [];
    for (let i = 0; i < players; i++) {
        const id = `playerP${i + 1}`;
        ids.push(id);
        board.registerPlayer(id, `Player ${i + 1}`);
    }
    // Register a watcher
    const watcherId = 'watcher';
    board.registerPlayer(watcherId, 'Board Watcher');
    const rows = board.numRows();
    const cols = board.numCols();
    const rand = (n) => Math.floor(Math.random() * n);
    const randCell = () => ({ r: rand(rows), c: rand(cols) });
    const delay = () => timeout(rand(maxDelayMs + 1));
    const colors = {
        reset: '\x1b[0m',
        bright: '\x1b[1m',
        dim: '\x1b[2m',
        cyan: '\x1b[36m',
        green: '\x1b[32m',
        yellow: '\x1b[33m',
        red: '\x1b[31m',
        blue: '\x1b[34m',
        magenta: '\x1b[35m',
        white: '\x1b[37m'
    };
    const playerColors = {
        'playerP1': colors.cyan,
        'playerP2': colors.green,
        'playerP3': colors.yellow,
        'playerP4': colors.red,
        'watcher': colors.white
    };
    const log = (pid, message, details) => {
        const color = playerColors[pid] ?? colors.reset;
        const timestamp = new Date().toISOString().slice(TIMESTAMP_START, TIMESTAMP_END);
        const detailsStr = details ?? '';
        const detailsFormatted = detailsStr.length > 0 ? ` ${colors.dim}${detailsStr}${colors.reset}` : '';
        console.log(`${colors.dim}[${timestamp}]${colors.reset} ${color}${pid}${colors.reset} ${message}${detailsFormatted}`);
    };
    const showBoard = () => {
        console.log('\n' + colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset);
        console.log(colors.bright + 'BOARD STATE:' + colors.reset);
        console.log(colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset);
        for (let r = 0; r < rows; r++) {
            let rowStr = '';
            for (let c = 0; c < cols; c++) {
                const pic = board.pictureAt(r, c);
                const isFaceUp = board.isFaceUp(r, c);
                const ctrl = board.controllerAt(r, c);
                let cellDisplay = '';
                const picValue = pic ?? null;
                const ctrlValue = ctrl ?? null;
                if (picValue === null) {
                    cellDisplay = colors.dim + '[empty]' + colors.reset;
                }
                else if (!isFaceUp) {
                    cellDisplay = colors.blue + '[down]' + colors.reset;
                }
                else if (ctrlValue !== null) {
                    const ctrlColor = playerColors[ctrlValue] ?? colors.reset;
                    cellDisplay = ctrlColor + `[${picValue}:${ctrlValue}]` + colors.reset;
                }
                else {
                    cellDisplay = colors.magenta + `[${picValue}]` + colors.reset;
                }
                rowStr += cellDisplay.padEnd(CELL_PADDING);
            }
            console.log(`  ${rowStr}`);
        }
        console.log(colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset + '\n');
    };
    /**
     * Perform a random first card flip for a player.
     * @param pid - Player ID
     */
    async function doRandomFirstFlip(pid) {
        const { r, c } = randCell();
        const pic = board.pictureAt(r, c);
        const picStr = pic ?? 'empty';
        try {
            log(pid, ` Flipping FIRST card at (${r},${c})`, `[${picStr}]`);
            await board.flipUp(pid, r, c);
        }
        catch (e) {
            const error = e instanceof Error ? e.message : String(e);
            log(pid, ` FIRST card${colors.red} failed${colors.reset} at (${r},${c})`, `[${error}]`);
        }
    }
    /**
     * Perform a random second card flip for a player.
     * @param pid - Player ID
     */
    async function doRandomSecondFlip(pid) {
        const { r, c } = randCell();
        const pic = board.pictureAt(r, c);
        const picStr = pic ?? 'empty';
        try {
            log(pid, ` Flipping SECOND card at (${r},${c})`, `[${picStr}]`);
            await board.flipUp(pid, r, c);
        }
        catch (e) {
            const error = e instanceof Error ? e.message : String(e);
            log(pid, ` SECOND card${colors.red} failed${colors.reset} at (${r},${c})`, `[${error}]`);
        }
    }
    /**
     * Watch the board for changes and log them.
     * Continuously re-registers after each notification.
     */
    async function watcherTask() {
        log(watcherId, ` Started watching board changes`, '');
        let changeCount = 0;
        let keepWatching = true;
        // Watch for changes until game ends
        while (keepWatching) {
            try {
                const watchPromise = new Promise((resolve) => {
                    board.addChangeWatcher(watcherId, resolve);
                });
                // Race between watch and a timeout to prevent hanging at end
                const result = await Promise.race([
                    watchPromise,
                    timeout(MAX_WATCH_TIMEOUT_MS).then(() => 'timeout')
                ]);
                if (result === 'timeout') {
                    keepWatching = false;
                }
                else {
                    changeCount++;
                    log(watcherId, ` ${colors.bright}Board changed!${colors.reset} (change #${changeCount})`, '');
                }
            }
            catch (e) {
                keepWatching = false;
            }
        }
        log(watcherId, ` Stopped watching (detected ${changeCount} changes)`, '');
    }
    /**
     * Run a player's game loop.
     * @param pid - Player ID
     */
    async function playerTask(pid) {
        log(pid, ` Started playing`, `(${triesPerPlayer} rounds)`);
        for (let t = 0; t < triesPerPlayer; t++) {
            await delay();
            await doRandomFirstFlip(pid);
            await delay();
            await doRandomSecondFlip(pid);
            if (t % BOARD_CHECK_INTERVAL === BOARD_CHECK_OFFSET) {
                showBoard();
            }
            await delay();
        }
        // Ensure 3-A/3-B cleanup runs even if the last move ended in a match
        await doRandomFirstFlip(pid);
        log(pid, ` Finished playing`, '');
    }
    console.log('\n' + colors.bright + colors.cyan + '╔═══════════════════════════════════════════════════════╗' + colors.reset);
    console.log(colors.bright + colors.cyan + '║         MEMORY SCRAMBLE SIMULATION START              ║' + colors.reset);
    console.log(colors.bright + colors.cyan + '╚═══════════════════════════════════════════════════════╝' + colors.reset + '\n');
    console.log(`${colors.bright}Configuration:${colors.reset}`);
    console.log(`  Players: ${players}`);
    console.log(`  Rounds per player: ${triesPerPlayer}`);
    console.log(`  Board: ${filename} (${rows}×${cols})`);
    console.log(`  ${colors.white}Watcher: Active${colors.reset}`);
    console.log('');
    showBoard();
    // Run everyone concurrently, including the watcher
    await Promise.all([
        ...ids.map(playerTask),
        watcherTask()
    ]);
    // Final board for inspection
    console.log('\n' + colors.bright + colors.cyan + '╔═══════════════════════════════════════════════════════╗' + colors.reset);
    console.log(colors.bright + colors.cyan + '║         SIMULATION COMPLETE - FINAL BOARD             ║' + colors.reset);
    console.log(colors.bright + colors.cyan + '╚═══════════════════════════════════════════════════════╝' + colors.reset);
    showBoard();
    // Show player statistics
    console.log(colors.bright + 'Player Statistics:' + colors.reset);
    for (const id of ids) {
        console.log(`  ${playerColors[id]}${id}${colors.reset}: Game completed`);
    }
}
/**
 * Execute a simulation of Memory Scramble where all players watch for board changes.
 * Each player watches the board concurrently while others make moves.
 *
 * @throws Error if the board file cannot be loaded or parsed
 */
async function simulationWatchMain() {
    const filename = 'boards/ab.txt';
    const board = await Board.parseFromFile(filename);
    const players = 4;
    const movesPerPlayer = 100;
    const maxDelayMs = 5;
    const timeout = (ms) => new Promise(res => setTimeout(res, ms));
    // Register players
    const ids = [];
    for (let i = 0; i < players; i++) {
        const id = `playerP${i + 1}`;
        ids.push(id);
        board.registerPlayer(id, `Player ${i + 1}`);
    }
    const rows = board.numRows();
    const cols = board.numCols();
    const rand = (n) => Math.floor(Math.random() * n);
    const randCell = () => ({ r: rand(rows), c: rand(cols) });
    const delay = () => timeout(rand(maxDelayMs + 1));
    const colors = {
        reset: '\x1b[0m',
        bright: '\x1b[1m',
        dim: '\x1b[2m',
        cyan: '\x1b[36m',
        green: '\x1b[32m',
        yellow: '\x1b[33m',
        red: '\x1b[31m',
        blue: '\x1b[34m',
        magenta: '\x1b[35m',
        white: '\x1b[37m'
    };
    const playerColors = {
        'playerP1': colors.cyan,
        'playerP2': colors.green,
        'playerP3': colors.yellow,
        'playerP4': colors.red
    };
    const log = (pid, message, details) => {
        const padEnd = 4;
        const color = playerColors[pid] ?? colors.reset;
        const timestamp = new Date().toISOString().slice(TIMESTAMP_START, TIMESTAMP_END);
        const detailsStr = details ?? '';
        const detailsFormatted = detailsStr.length > 0 ? ` ${colors.dim}${detailsStr}${colors.reset}` : '';
        console.log(`${colors.dim}[${timestamp}]${colors.reset} ${color}${pid.padEnd(padEnd)}${colors.reset} ${message}${detailsFormatted}`);
    };
    const showBoard = () => {
        console.log('\n' + colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset);
        console.log(colors.bright + 'BOARD STATE:' + colors.reset);
        console.log(colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset);
        for (let r = 0; r < rows; r++) {
            let rowStr = '';
            for (let c = 0; c < cols; c++) {
                const pic = board.pictureAt(r, c);
                const isFaceUp = board.isFaceUp(r, c);
                const ctrl = board.controllerAt(r, c);
                let cellDisplay = '';
                if (pic === null) {
                    cellDisplay = colors.dim + '[empty]' + colors.reset;
                }
                else if (!isFaceUp) {
                    cellDisplay = colors.blue + '[down]' + colors.reset;
                }
                else if (ctrl !== null) {
                    const ctrlColor = playerColors[ctrl] ?? colors.reset;
                    cellDisplay = ctrlColor + `[${pic}:${ctrl}]` + colors.reset;
                }
                else {
                    cellDisplay = colors.magenta + `[${pic}]` + colors.reset;
                }
                rowStr += cellDisplay.padEnd(CELL_PADDING);
            }
            console.log(`  ${rowStr}`);
        }
        console.log(colors.bright + '━'.repeat(SEPARATOR_WIDTH) + colors.reset + '\n');
    };
    /**
     * Player watcher task - continuously watches for board changes.
     * Each player watches the board and logs when they detect changes.
     * @param pid - Player ID
     * @param maxChanges - Maximum number of changes to watch for
     */
    async function watcherTask(pid, maxChanges) {
        log(pid, `${colors.white} Started watching${colors.reset}`, `(max ${maxChanges} changes)`);
        let changeCount = 0;
        while (changeCount < maxChanges) {
            try {
                const watchPromise = new Promise((resolve) => {
                    board.addChangeWatcher(pid, resolve);
                });
                const result = await Promise.race([
                    watchPromise,
                    timeout(MAX_WATCH_TIMEOUT_MS).then(() => 'timeout')
                ]);
                if (result === 'timeout') {
                    log(pid, `${colors.dim} Watch timeout (no more changes)${colors.reset}`, '');
                    break;
                }
                changeCount++;
                log(pid, `${colors.bright} DETECTED CHANGE #${changeCount}${colors.reset}`, '');
                // Small delay before re-registering
                await timeout(1);
            }
            catch (e) {
                log(pid, `${colors.red}👁  Watch error${colors.reset}`, String(e));
                break;
            }
        }
        log(pid, `${colors.white} Stopped watching${colors.reset}`, `(detected ${changeCount} changes)`);
    }
    /**
     * Player action task - makes random moves on the board.
     * @param pid - Player ID
     */
    async function playerTask(pid) {
        log(pid, ` Started playing`, `(${movesPerPlayer} moves)`);
        for (let move = 0; move < movesPerPlayer; move++) {
            await delay();
            // First card
            const { r: r1, c: c1 } = randCell();
            const pic1 = board.pictureAt(r1, c1);
            const pic1Str = pic1 ?? 'empty';
            try {
                log(pid, ` Flip FIRST at (${r1},${c1})`, `[${pic1Str}]`);
                await board.flipUp(pid, r1, c1);
            }
            catch (e) {
                const error = e instanceof Error ? e.message : String(e);
                log(pid, ` FIRST ${colors.red}failed${colors.reset}`, `[${error}]`);
                continue;
            }
            await delay();
            // Second card
            const { r: r2, c: c2 } = randCell();
            const pic2 = board.pictureAt(r2, c2);
            const pic2Str = pic2 ?? 'empty';
            try {
                log(pid, ` Flip SECOND at (${r2},${c2})`, `[${pic2Str}]`);
                await board.flipUp(pid, r2, c2);
                if (pic1 === pic2 && pic1 !== null) {
                    log(pid, ` ${colors.bright}${colors.green}✓ MATCH!${colors.reset}`, `[${pic1}]`);
                }
                else {
                    log(pid, ` ${colors.dim}✗ No match${colors.reset}`, `[${pic1Str} ≠ ${pic2Str}]`);
                }
            }
            catch (e) {
                const error = e instanceof Error ? e.message : String(e);
                log(pid, ` SECOND ${colors.red}failed${colors.reset}`, `[${error}]`);
            }
            await delay();
        }
        // Cleanup flip
        const { r, c } = randCell();
        try {
            await board.flipUp(pid, r, c);
        }
        catch (e) {
            // Ignore errors in cleanup flip
        }
        log(pid, ` Finished playing`, '');
    }
    console.log('\n' + colors.bright + colors.cyan + '╔═══════════════════════════════════════════════════════╗' + colors.reset);
    console.log(colors.bright + colors.cyan + '║    MEMORY SCRAMBLE SIMULATION - ALL PLAYERS WATCH     ║' + colors.reset);
    console.log(colors.bright + colors.cyan + '╚═══════════════════════════════════════════════════════╝' + colors.reset + '\n');
    console.log(`${colors.bright}Configuration:${colors.reset}`);
    console.log(`  Players: ${players} (all watching + playing)`);
    console.log(`  Moves per player: ${movesPerPlayer}`);
    console.log(`  Board: ${filename} (${rows}×${cols})`);
    console.log(`  ${colors.white}Mode: Each player watches while others play${colors.reset}`);
    console.log('');
    showBoard();
    // Run all players concurrently - each both plays AND watches
    const tasks = [];
    for (const id of ids) {
        // Each player has two concurrent tasks: playing and watching
        tasks.push(playerTask(id));
        tasks.push(watcherTask(id, movesPerPlayer * players * 2)); // Watch for many changes
    }
    await Promise.all(tasks);
    console.log('\n' + colors.bright + colors.cyan + '╔═══════════════════════════════════════════════════════╗' + colors.reset);
    console.log(colors.bright + colors.cyan + '║         SIMULATION COMPLETE - FINAL BOARD             ║' + colors.reset);
    console.log(colors.bright + colors.cyan + '╚═══════════════════════════════════════════════════════╝' + colors.reset);
    showBoard();
    console.log(colors.bright + 'Summary:' + colors.reset);
    console.log(`  All ${players} players completed their games while watching for changes`);
    console.log(`  Each player detected board changes made by others in real-time`);
}
// Determine which simulation to run based on command line argument
const mode = process.argv[2];
if (mode === 'watch') {
    void simulationWatchMain();
}
else {
    void simulationMain();
}
//# sourceMappingURL=simulation.js.map