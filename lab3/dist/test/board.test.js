import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { Board } from '../src/board.js';
import express from 'express';
import { map } from '../src/commands.js';
function tmpfile(contents) {
    const f = path.join(os.tmpdir(), `board-${Math.random().toString(36).slice(2)}.txt`);
    fs.writeFileSync(f, contents);
    return f;
}
describe('Board Parsing Tests', function () {
    it('parses 3x3 board', async function () {
        const f = tmpfile('3x3\nA\nB\nC\nA\nB\nC\nD\nD\nF\n');
        const b = await Board.parseFromFile(f);
        assert.equal(b.numRows(), 3);
        assert.equal(b.numCols(), 3);
        assert.equal(b.pictureAt(0, 0), 'A');
        assert.equal(b.pictureAt(0, 1), 'B');
        assert.equal(b.pictureAt(0, 2), 'C');
        assert.equal(b.pictureAt(1, 0), 'A');
        assert.equal(b.pictureAt(1, 1), 'B');
        assert.equal(b.pictureAt(1, 2), 'C');
        assert.equal(b.pictureAt(2, 0), 'D');
        assert.equal(b.pictureAt(2, 1), 'D');
        assert.equal(b.pictureAt(2, 2), 'F');
        assert.match(b.picturesDump(), /^3x3\nA\nB\nC\nA\nB\nC\nD\nD\nF\n$/);
    });
    it('rejects bad headers', async function () {
        for (const txt of ['aa\nA\n', '3x\nA\n', 'x3\nA\n', '0x2\nA\nA\n', '-1x2\nA\nA\n']) {
            const f = tmpfile(txt);
            await assert.rejects(Board.parseFromFile(f));
        }
    });
    it('rejects wrong number of cards', async function () {
        const few = tmpfile('2x2\nA\nB\nC\n');
        const many = tmpfile('2x2\nA\nB\nC\nD\nE\n');
        await assert.rejects(Board.parseFromFile(few));
        await assert.rejects(Board.parseFromFile(many));
    });
    it('rejects whitespace/empty card tokens', async function () {
        const withSpace = tmpfile('1x3\nA\n\nB\n');
        const empty = tmpfile('1x1\n\n');
        await assert.rejects(Board.parseFromFile(withSpace));
        await assert.rejects(Board.parseFromFile(empty));
    });
    it('out-of-bounds guards', async function () {
        const f = tmpfile('1x1\nX\n');
        const b = await Board.parseFromFile(f);
        assert.throws(() => b.pictureAt(-1, 0));
        assert.throws(() => b.isFaceUp(0, 1));
        assert.throws(() => b.controllerAt(1, 0));
        await assert.rejects(async () => await b.flipUp('nope', 1, 0));
    });
});
describe('Board – complete rule coverage (1-A…3-B)', function () {
    this.timeout(4000);
    describe('First card (1-A … 1-D)', () => {
        it('1-B: face-down -> becomes face-up and controlled by player', async () => {
            const b = await Board.parseFromFile(tmpfile('1x2\nA\nA\n'));
            b.registerPlayer('p');
            assert.strictEqual(b.isFaceUp(0, 0), false);
            await b.flipUp('p', 0, 0);
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), 'p');
        });
        it('1-C: already face-up and uncontrolled -> take control', async () => {
            // Force an uncontrolled, face-up card via a mismatch (2-E).
            const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
            b.registerPlayer('p1');
            b.registerPlayer('p2');
            await b.flipUp('p1', 0, 0); // first
            await b.flipUp('p1', 0, 1); // second (mismatch -> 2-E): both face up, uncontrolled
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.isFaceUp(0, 1), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.controllerAt(0, 1), null);
            // Now p2 chooses that face-up, uncontrolled card as their FIRST card -> 1-C
            await b.flipUp('p2', 0, 0);
            assert.strictEqual(b.controllerAt(0, 0), 'p2');
        });
        it('1-D: face-up and controlled by another -> WAIT; resumes when control is relinquished', async () => {
            const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
            b.registerPlayer('p1');
            b.registerPlayer('p2');
            await b.flipUp('p1', 0, 0); // p1 controls (0,0)
            // p2 should WAIT - start this as a concurrent operation
            const p2FlipPromise = b.flipUp('p2', 0, 0);
            // p1 causes a mismatch to relinquish control (2-E)
            await b.flipUp('p1', 0, 1);
            // Now p2 takes control
            await p2FlipPromise;
            //p2's flipUp should now complete
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), 'p2');
        });
        it('1-A: empty space as FIRST -> fails (after pair was removed earlier)', async () => {
            // Build a board, make a match, then remove on the next FIRST (3-A) to create empties.
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p');
            // Make A-A match
            await b.flipUp('p', 0, 0);
            await b.flipUp('p', 0, 1);
            // Next FIRST does 3-A removal BEFORE proceeding
            await b.flipUp('p', 0, 2); // removes (0,0) & (0,1), then flips (0,2) as the new first
            // Now (0,0) is empty -> 1-A if someone tries FIRST there
            await assert.rejects(b.flipUp('p', 0, 0), /empty space/i);
        });
    });
    describe('Second card (2-A … 2-E)', () => {
        it('2-A: second is empty -> fail & relinquish FIRST (first remains face-up for now)', async () => {
            // Layout A A B B. First create a match on B B, then start a new FIRST which triggers 3-A removal -> empties.
            const b = await Board.parseFromFile(tmpfile('1x4\nA\nA\nB\nB\n'));
            b.registerPlayer('p');
            // Make B-B match
            await b.flipUp('p', 0, 2);
            await b.flipUp('p', 0, 3);
            // New FIRST triggers 3-A removal of (2,3), then flips (0,0) as FIRST
            await b.flipUp('p', 0, 0);
            assert.strictEqual(b.controllerAt(0, 0), 'p');
            // Cells (0,2) and (0,3) are now empty; pick an empty as SECOND → 2-A
            await assert.rejects(b.flipUp('p', 0, 2), /empty space/i);
            // FIRST was relinquished but remains face up (will flip down on next FIRST via 3-B)
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
        });
        it('2-B: second is face-up and controlled -> fail & relinquish FIRST (no waiting)', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p1');
            b.registerPlayer('p2');
            // p2 controls the middle card
            await b.flipUp('p2', 0, 1);
            // p1 takes FIRST at (0,0)
            await b.flipUp('p1', 0, 0);
            assert.strictEqual(b.controllerAt(0, 0), 'p1');
            // p1 tries SECOND at p2-controlled (0,1) -> 2-B
            await assert.rejects(b.flipUp('p1', 0, 1), /controlled/i);
            // p1 relinquished FIRST; card stays face up, uncontrolled
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
        });
        it('2-C: SECOND was face-down -> it flips up', async () => {
            const b = await Board.parseFromFile(tmpfile('1x2\nA\nA\n'));
            b.registerPlayer('p');
            await b.flipUp('p', 0, 0); // first (A)
            assert.strictEqual(b.isFaceUp(0, 1), false);
            await b.flipUp('p', 0, 1);
            assert.strictEqual(b.isFaceUp(0, 1), true); // 2-C ensured flip-up
        });
        it('2-D: match -> keep control of both (remain face-up until next FIRST)', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p');
            await b.flipUp('p', 0, 0);
            await b.flipUp('p', 0, 1);
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.isFaceUp(0, 1), true);
            assert.strictEqual(b.controllerAt(0, 0), 'p');
            assert.strictEqual(b.controllerAt(0, 1), 'p');
            await b.flipUp('p', 0, 2); // proceed to next FIRST to verify they dissappear later
            assert.strictEqual(b.pictureAt(0, 0), null);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.pictureAt(0, 1), null);
            assert.strictEqual(b.controllerAt(0, 1), null);
        });
        it('2-E: mismatch -> relinquish both; they remain face-up (uncontrolled) until 3-B', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nB\nC\n'));
            b.registerPlayer('p');
            await b.flipUp('p', 0, 0);
            await b.flipUp('p', 0, 1); // mismatch
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.isFaceUp(0, 1), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.controllerAt(0, 1), null);
        });
    });
    describe('Cleanup before next FIRST (3-A & 3-B)', () => {
        it('3-A: previously matched pair gets removed on the next FIRST', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p');
            // Make match A-A
            await b.flipUp('p', 0, 0);
            await b.flipUp('p', 0, 1);
            // Next FIRST removes the pair, then proceeds to flip B as FIRST
            await b.flipUp('p', 0, 2);
            // A-A removed
            assert.strictEqual(b.pictureAt(0, 0), null);
            assert.strictEqual(b.pictureAt(0, 1), null);
            assert.strictEqual(b.isFaceUp(0, 0), false);
            assert.strictEqual(b.isFaceUp(0, 1), false);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.controllerAt(0, 1), null);
            // And (0,2) is now the current FIRST (face up and controlled)
            assert.strictEqual(b.isFaceUp(0, 2), true);
            assert.strictEqual(b.controllerAt(0, 2), 'p');
        });
        it('3-B: previously non-matching face-up, uncontrolled cards flip down on the next FIRST', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nB\nC\n'));
            b.registerPlayer('p');
            // Create mismatch -> both A and B are face-up, uncontrolled (2-E)
            await b.flipUp('p', 0, 0);
            await b.flipUp('p', 0, 1);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.controllerAt(0, 1), null);
            // Next FIRST at (0,2) should perform 3-B flip-down for (0,0) and (0,1)
            await b.flipUp('p', 0, 2);
            assert.strictEqual(b.isFaceUp(0, 0), false);
            assert.strictEqual(b.isFaceUp(0, 1), false);
            // And the new FIRST is face-up and controlled
            assert.strictEqual(b.isFaceUp(0, 2), true);
            assert.strictEqual(b.controllerAt(0, 2), 'p');
        });
        it('3-B (single-card case): if 2-A/2-B happened, only the lingering FIRST flips down on the next FIRST', async () => {
            // Use 2-B to leave a single face-up, uncontrolled FIRST behind.
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p1');
            b.registerPlayer('p2');
            await b.flipUp('p2', 0, 1); // p2 controls middle card
            await b.flipUp('p1', 0, 0); // p1 FIRST
            await assert.rejects(async () => await b.flipUp('p1', 0, 1)); // 2-B -> p1 relinquishes (0,0), which stays up & uncontrolled
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
            // Next FIRST should flip (0,0) down (3-B), then proceed
            await b.flipUp('p1', 0, 2);
            assert.strictEqual(b.isFaceUp(0, 0), false);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.isFaceUp(0, 2), true);
            assert.strictEqual(b.controllerAt(0, 2), 'p1');
        });
        it('3-B (same card case): If user chooses same second card as the first card, it should be relinquished and flipped down', async () => {
            const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
            b.registerPlayer('p');
            await b.flipUp('p', 0, 0); // p FIRST
            await assert.rejects(async () => await b.flipUp('p', 0, 0)); //  p SECOND, p relinquishes (0,0), which stays up & uncontrolled
            assert.strictEqual(b.isFaceUp(0, 0), true);
            assert.strictEqual(b.controllerAt(0, 0), null);
            // Next FIRST should flip (0,0) down (3-B), then proceed
            await b.flipUp('p', 0, 2);
            assert.strictEqual(b.isFaceUp(0, 0), false);
            assert.strictEqual(b.controllerAt(0, 0), null);
            assert.strictEqual(b.isFaceUp(0, 2), true);
            assert.strictEqual(b.controllerAt(0, 2), 'p');
        });
    });
});
describe('Board map function', function () {
    it('preserves face-up/face-down state after transformation', async function () {
        const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
        b.registerPlayer('p');
        await b.flipUp('p', 0, 0); // flip A face-up
        await b.map(async (card) => card + '-transformed');
        // Card should still be face-up and controlled
        assert.equal(b.pictureAt(0, 0), 'A-transformed');
        assert.equal(b.isFaceUp(0, 0), true);
        assert.equal(b.controllerAt(0, 0), 'p');
        // Other card still face-down
        assert.equal(b.pictureAt(0, 1), 'B-transformed');
        assert.equal(b.isFaceUp(0, 1), false);
    });
});
describe('Server /replace endpoint', function () {
    this.timeout(5000);
    let server;
    let port;
    afterEach(function () {
        server?.close();
    });
    it('replaces cards via HTTP request', async function () {
        const filename = tmpfile('2x2\nunicorn\nrainbow\nunicorn\nrainbow\n');
        const board = await Board.parseFromFile(filename);
        port = 3000 + Math.floor(Math.random() * 1000);
        const app = express();
        app.get('/replace/:playerId/:fromCard/:toCard', async (request, response) => {
            const { playerId, fromCard, toCard } = request.params;
            const boardState = await map(board, playerId, async (card) => card === fromCard ? toCard : card);
            response.status(200).type('text').send(boardState);
        });
        await new Promise((resolve) => {
            server = app.listen(port, () => resolve());
        });
        // Replace unicorn with sunshine
        const response = await fetch(`http://localhost:${port}/replace/player1/unicorn/sunshine`);
        assert.strictEqual(response.status, 200);
        // Verify replacement worked
        assert.strictEqual(board.pictureAt(0, 0), 'sunshine');
        assert.strictEqual(board.pictureAt(0, 1), 'rainbow');
        assert.strictEqual(board.pictureAt(1, 0), 'sunshine');
        assert.strictEqual(board.pictureAt(1, 1), 'rainbow');
    });
});
describe('Board watch functionality', function () {
    this.timeout(5000);
    it('watch resolves when a card flips face-up', async function () {
        const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
        b.registerPlayer('p1');
        b.registerPlayer('p2');
        // Start watching before the change
        const watchPromise = new Promise((resolve) => {
            b.addChangeWatcher('p2', resolve);
        });
        // p1 flips a card
        await b.flipUp('p1', 0, 0);
        // p2's watch should resolve with the updated state
        const state = await watchPromise;
        assert.match(state, /1x2/);
        assert.match(state, /up A/); // Card is face-up
    });
    it('watch resolves when a card flips face-down', async function () {
        const b = await Board.parseFromFile(tmpfile('1x3\nA\nB\nC\n'));
        b.registerPlayer('p1');
        b.registerPlayer('p2');
        // Create a mismatch to get face-up, uncontrolled cards
        await b.flipUp('p1', 0, 0);
        await b.flipUp('p1', 0, 1);
        // Start watching
        const watchPromise = new Promise((resolve) => {
            b.addChangeWatcher('p2', resolve);
        });
        // Next first card triggers 3-B (flip down)
        await b.flipUp('p1', 0, 2);
        // Watch should resolve
        const state = await watchPromise;
        assert.match(state, /down/); // Cards flipped down
    });
    it('watch resolves when cards are removed (match)', async function () {
        const b = await Board.parseFromFile(tmpfile('1x3\nA\nA\nB\n'));
        b.registerPlayer('p1');
        b.registerPlayer('p2');
        // Make a match
        await b.flipUp('p1', 0, 0);
        await b.flipUp('p1', 0, 1);
        // Start watching
        const watchPromise = new Promise((resolve) => {
            b.addChangeWatcher('p2', resolve);
        });
        // Next first card triggers 3-A (removal)
        await b.flipUp('p1', 0, 2);
        // Watch should resolve
        const state = await watchPromise;
        assert.match(state, /none/); // Cards removed
    });
    it('watch resolves when pictures change (map)', async function () {
        const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
        b.registerPlayer('p1');
        b.registerPlayer('p2');
        // Start watching
        const watchPromise = new Promise((resolve) => {
            b.addChangeWatcher('p2', resolve);
        });
        // Transform cards
        await b.map(async (card) => card + '-new');
        // Watch should resolve
        await watchPromise;
        // Verify the transformation happened
        assert.strictEqual(b.pictureAt(0, 0), 'A-new');
        assert.strictEqual(b.pictureAt(0, 1), 'B-new');
    });
    it('multiple watchers all get notified', async function () {
        const b = await Board.parseFromFile(tmpfile('1x2\nA\nB\n'));
        b.registerPlayer('p1');
        b.registerPlayer('p2');
        b.registerPlayer('p3');
        // Start multiple watchers
        const watch1 = new Promise((resolve) => {
            b.addChangeWatcher('p1', resolve);
        });
        const watch2 = new Promise((resolve) => {
            b.addChangeWatcher('p2', resolve);
        });
        const watch3 = new Promise((resolve) => {
            b.addChangeWatcher('p3', resolve);
        });
        // Make a change
        await b.flipUp('p1', 0, 0);
        // All watches should resolve
        const [state1, state2, state3] = await Promise.all([watch1, watch2, watch3]);
        assert.match(state1, /my A/); // p1 sees their control
        assert.match(state2, /up A/); // p2 sees it face-up
        assert.match(state3, /up A/); // p3 sees it face-up
    });
});
//# sourceMappingURL=board.test.js.map