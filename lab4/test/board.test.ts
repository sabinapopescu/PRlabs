/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from "node:assert";
import fs from "node:fs";
import { Board } from "../src/board.js";

/**
 * Tests for the Board abstract data type.
 */
describe("Board", function () {
  // Testing strategy
  //   Partition for parseFromFile():
  //     - valid board files: small (1x1), medium (3x3), large (5x5)
  //     - invalid files: missing file, empty file, invalid dimensions, wrong card count
  //     - card characters: alphanumeric, emoji, special characters
  //
  //   Partition for look():
  //     - board state: all face-down, some face-up, some removed (none)
  //     - controller: no controller, controlled by self, controlled by others
  //     - player: new player, existing player
  //
  //   Partition for flip():
  //     First card flip:
  //       - spot state: none (empty), face-down, face-up not controlled, face-up controlled by self, face-up controlled by other
  //       - previous play: no previous, matched pair, non-matched cards
  //     Second card flip:
  //       - spot state: none, face-down, face-up not controlled, face-up controlled
  //       - match: cards match, cards don't match
  //       - first card still exists or was removed
  //
  //   Partition for coordinates:
  //     - valid: (0,0) top-left corner, middle, (rows-1,cols-1) bottom-right corner
  //     - invalid: negative, out of bounds

  describe("parseFromFile", function () {
    it("parses valid 3x3 board with emoji", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");
      const state = board.look("testPlayer");
      assert(state.startsWith("3x3\n"));
      // Should have 9 cards, all face-down initially
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines.length, 10); // dimension line + 9 cards
      lines.slice(1).forEach((line) => assert.strictEqual(line, "down"));
    });

    it("parses valid 5x5 board", async function () {
      const board = await Board.parseFromFile("boards/ab.txt");
      const state = board.look("player1");
      assert(state.startsWith("5x5\n"));
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines.length, 26); // 1 + 25 cards
    });

    it("throws error for non-existent file", async function () {
      await assert.rejects(
        async () => Board.parseFromFile("boards/nonexistent.txt"),
        /ENOENT/
      );
    });

    it("throws error for invalid dimensions format", async function () {
      const tempFile = "test-invalid-dimensions.txt";
      await fs.promises.writeFile(tempFile, "invalid\nA\nB\n");

      await assert.rejects(
        async () => Board.parseFromFile(tempFile),
        /invalid board dimensions format/
      );

      await fs.promises.unlink(tempFile);
    });

    it("throws error for wrong number of cards", async function () {
      const tempFile = "test-wrong-count.txt";
      await fs.promises.writeFile(tempFile, "2x2\nA\nB\nC\n"); // only 3 cards, need 4

      await assert.rejects(
        async () => Board.parseFromFile(tempFile),
        /missing card at line 5|expected 4 cards/
      );

      await fs.promises.unlink(tempFile);
    });
    it("throws error for card with whitespace", async function () {
      const tempFile = "test-whitespace.txt";
      await fs.promises.writeFile(tempFile, "1x2\nA\nB C\n");

      await assert.rejects(
        async () => Board.parseFromFile(tempFile),
        /invalid card format/
      );

      await fs.promises.unlink(tempFile);
    });
  });

  describe("look", function () {
    it("shows all cards face-down for new player on fresh board", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");
      const state = board.look("alice");

      const lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines[0], "3x3");
      lines.slice(1).forEach((line) => assert.strictEqual(line, "down"));
    });

    it('shows face-up card controlled by player as "my"', async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Flip a card for alice
      await board.flip("alice", 0, 0);
      const state = board.look("alice");

      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("my "), `Expected "my" but got: ${lines[1]}`);
    });

    it('shows face-up card controlled by other player as "up"', async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips a card
      await board.flip("alice", 0, 0);

      // Bob looks at the board
      const state = board.look("bob");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("up "), `Expected "up" but got: ${lines[1]}`);
    });

    it('shows removed cards as "none"', async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice matches the two unicorns at (0,0) and (0,1)
      await board.flip("alice", 0, 0); // first card
      await board.flip("alice", 0, 1); // second card (match!)
      await board.flip("alice", 1, 0); // trigger cleanup - cards should be removed

      const state = board.look("alice");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines[1], "none", "First card should be removed");
      assert.strictEqual(lines[2], "none", "Second card should be removed");
    });

    it('shows face-up card controlled by other player as "up"', async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips a card
      await board.flip("alice", 0, 0);

      // Bob looks at the board
      const state = board.look("bob");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("up "), `Expected "up" but got: ${lines[1]}`);
    });

    it('shows removed cards as "none"', async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice matches the two unicorns at (0,0) and (0,1)
      await board.flip("alice", 0, 0); // first card
      await board.flip("alice", 0, 1); // second card (match!)
      await board.flip("alice", 1, 0); // trigger cleanup - cards should be removed

      const state = board.look("alice");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines[1], "none", "First card should be removed");
      assert.strictEqual(lines[2], "none", "Second card should be removed");
    });
  });

  describe("flip - first card", function () {
    it("throws error when flipping empty spot", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Create an empty spot by matching and removing cards
      await board.flip("alice", 0, 0);
      await board.flip("alice", 0, 1); // match
      await board.flip("alice", 1, 0); // cleanup - removes (0,0) and (0,1)

      // Try to flip the now-empty spot
      await assert.rejects(
        async () => await board.flip("alice", 0, 0),
        /no card at this position/
      );
    });

    it("flips face-down card to face-up and gives control", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      const state = await board.flip("alice", 0, 0);
      const lines = state.split("\n").filter((line) => line.length > 0);

      assert(lines[1]?.startsWith("my "), "Card should be controlled by alice");
    });

    it("takes control of face-up uncontrolled card", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips two non-matching cards
      await board.flip("alice", 0, 0);
      await board.flip("alice", 1, 0); // don't match

      // Bob flips a different card (this cleans up alice's cards - they stay face-up but uncontrolled)
      await board.flip("bob", 2, 2);

      // Alice takes control of her previous card again
      const state = await board.flip("alice", 0, 0);
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("my "), "Alice should control the card");
    });

    it("waits when card is controlled by another player", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips a card
      await board.flip("alice", 0, 0);

      // Bob tries to flip the same card - this should WAIT, not throw
      // We'll start it but not await immediately
      const bobPromise = board.flip("bob", 0, 0);

      // Alice releases the card
      await board.flip("alice", 1, 0); // Alice flips a second card

      // Now Bob should be able to get control
      await bobPromise; // This should succeed after alice releases
    });

    it("throws error for invalid coordinates", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      await assert.rejects(
        async () => await board.flip("alice", -1, 0),
        /invalid position/
      );

      await assert.rejects(
        async () => await board.flip("alice", 10, 10),
        /invalid position/
      );
    });
  });

  describe("flip - second card", function () {
    it("throws error when second card is empty spot", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Create empty spots
      await board.flip("alice", 0, 0);
      await board.flip("alice", 0, 1); // match
      await board.flip("alice", 1, 0); // cleanup

      // Try second card on empty spot
      await board.flip("alice", 2, 0); // first card
      await assert.rejects(
        async () => await board.flip("alice", 0, 0), // empty spot
        /no card at this position/
      );
    });

    it("throws error when second card is controlled", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips first card
      await board.flip("alice", 0, 0);

      // Bob flips a card
      await board.flip("bob", 1, 0);

      // Alice tries to flip Bob's card as second card
      await assert.rejects(
        async () => await board.flip("alice", 1, 0),
        /card is controlled by a player/
      );
    });

    it("matches two identical cards", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // The board has 🦄 at (0,0) and (0,1)
      await board.flip("alice", 0, 0); // first card
      const state = await board.flip("alice", 0, 1); // second card - should match

      const lines = state.split("\n").filter((line) => line.length > 0);
      // Both cards should be controlled by alice
      assert(lines[1]?.startsWith("my "), "First card should be controlled");
      assert(lines[2]?.startsWith("my "), "Second card should be controlled");
    });

    it("does not match different cards", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // (0,0) is 🦄, (1,0) is 🌈
      await board.flip("alice", 0, 0); // first card
      const state = await board.flip("alice", 1, 0); // second card - don't match

      const lines = state.split("\n").filter((line) => line.length > 0);
      // Both cards should be face-up but not controlled
      assert(lines[1]?.startsWith("up "), "First card should be uncontrolled");
      assert(lines[4]?.startsWith("up "), "Second card should be uncontrolled");
    });

    it("flips face-down second card to face-up", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      await board.flip("alice", 0, 0); // first card (face-down -> face-up)
      await board.flip("alice", 0, 2); // second card (face-down -> face-up)

      // Bob should see both cards face-up
      const state = board.look("bob");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("up "));
      assert(lines[3]?.startsWith("up "));
    });
  });

  describe("flip - cleanup rules", function () {
    it("removes matched pair when flipping next first card", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Match cards at (0,0) and (0,1)
      await board.flip("alice", 0, 0);
      await board.flip("alice", 0, 1);

      // Flip another card - should trigger removal
      const state = await board.flip("alice", 2, 0);
      const lines = state.split("\n").filter((line) => line.length > 0);

      assert.strictEqual(lines[1], "none", "Matched card 1 should be removed");
      assert.strictEqual(lines[2], "none", "Matched card 2 should be removed");
    });

    it("turns non-matched cards face-down when flipping next first card", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Flip non-matching cards
      await board.flip("alice", 0, 0); // 🦄
      await board.flip("alice", 1, 0); // 🌈 - no match

      // Cards are face-up but not controlled
      let state = board.look("bob");
      let lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("up "));

      // Alice flips another card - should turn previous cards face-down
      await board.flip("alice", 2, 0);

      state = board.look("bob");
      lines = state.split("\n").filter((line) => line.length > 0);
      assert.strictEqual(lines[1], "down", "Previous card should be face-down");
      assert.strictEqual(lines[4], "down", "Previous card should be face-down");
    });

    it("does not turn face-down cards controlled by other players", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips non-matching cards
      await board.flip("alice", 0, 0);
      await board.flip("alice", 1, 0);

      // Bob takes control of one of alice's previous cards
      await board.flip("bob", 0, 0);

      // Alice flips next card - should not affect bob's card
      await board.flip("alice", 2, 0);

      const state = board.look("bob");
      const lines = state.split("\n").filter((line) => line.length > 0);
      assert(lines[1]?.startsWith("my "), "Bob should still control his card");
    });
  });

  describe("multi-player scenarios", function () {
    it("allows multiple players to play simultaneously", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice plays and matches
      await board.flip("alice", 0, 0); // first card
      await board.flip("alice", 0, 1); // second card - match! (both controlled by alice)

      // Alice should control both cards
      let aliceState = board.look("alice");
      assert(
        aliceState.includes("my "),
        "Alice should control her matched cards"
      );

      // Bob plays
      await board.flip("bob", 1, 0); // first card -
      await board.flip("bob", 2, 0); // second card - match!

      // Bob should control his cards
      let bobState = board.look("bob");
      assert(bobState.includes("my "), "Bob should control his matched cards");

      // Now when Alice makes her next move, her previous matched cards should be removed
      await board.flip("alice", 2, 1); // this triggers cleanup of alice's matched pair

      aliceState = board.look("alice");
      const aliceLines = aliceState.split("\n").filter((l) => l.length > 0);
      assert.strictEqual(
        aliceLines[1],
        "none",
        "Alice first card should now be removed"
      );
      assert.strictEqual(
        aliceLines[2],
        "none",
        "Alice second card should now be removed"
      );

      // Bob's cards should still be controlled (not affected by Alice's cleanup)
      bobState = board.look("bob");
      assert(bobState.includes("my "), "Bob should still control his cards");
    });

    it("tracks each player state independently", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice flips first card
      await board.flip("alice", 0, 0);

      // Bob flips his cards
      await board.flip("bob", 1, 1);
      await board.flip("bob", 1, 2);

      // Alice can still flip her second card
      const state = await board.flip("alice", 0, 1);
      assert(state.includes("my "));
    });

    it("handles multiple concurrent waiters for same card", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice controls a card
      await board.flip("alice", 0, 0);

      // Bob and Charlie both try to flip it (they will wait)
      const bobPromise = board.flip("bob", 0, 0);
      const charliePromise = board.flip("charlie", 0, 0);

      // Alice releases by flipping a second card
      await board.flip("alice", 1, 0);

      // Either Bob or Charlie should get it (we don't care which)
      const results = await Promise.race([bobPromise, charliePromise]);
      assert(results.includes("my "), "One player should control the card");
    });
  });

  describe("map", function () {
    it("transforms all cards on the board", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Flip a card to see it
      await board.flip("alice", 0, 0);

      // Transform all cards by appending "-new"
      await board.map("alice", async (card: string) => `${card}-new`);

      const state = board.look("alice");
      // Check that the face-up card has been transformed
      assert(state.includes("-new"), "Transformed card should be visible");
    });

    it("maintains pairwise consistency during transformation", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Start a map operation with a slow transformer
      const mapPromise = board.map("alice", async (card: string) => {
        // Simulate slow transformation
        await new Promise((resolve) => setTimeout(resolve, 5));
        return `transformed-${card}`;
      });

      // While map is running, look at the board
      // Cards should be consistent (matching pairs still match)
      // This is hard to test directly, but we ensure no errors occur
      const lookPromise = board.look("bob");

      await Promise.all([mapPromise, lookPromise]);
      // If we get here without errors, consistency was maintained
    });

    it("does not affect card state (face-up/down, controller)", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Alice controls a card
      await board.flip("alice", 0, 0);

      // Transform all cards
      await board.map("bob", async (card: string) => `new-${card}`);

      // Alice should still control her card
      const state = board.look("alice");
      assert(state.includes("my "), "Alice should still control her card");
    });

    it("applies same transformation to matching cards", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Track how many times transformer is called for each unique card
      const callCount = new Map<string, number>();

      await board.map("alice", async (card: string) => {
        const count = callCount.get(card) ?? 0;
        callCount.set(card, count + 1);
        return `${card}-v${count}`;
      });

      // Each unique card should be transformed exactly once
      // (because we cache transformations for pairwise consistency)
      for (const count of callCount.values()) {
        assert.strictEqual(
          count,
          1,
          "Each unique card should be transformed exactly once"
        );
      }
    });

    it("can interleave with flip operations", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Start a slow map
      const mapPromise = board.map("alice", async (card: string) => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        return `${card}-mapped`;
      });

      // While map is running, Bob can still flip cards
      const flipPromise = board.flip("bob", 0, 0);

      // Both should complete without errors
      await Promise.all([mapPromise, flipPromise]);
    });
  });

  describe("watch", function () {
    it("waits for a change on the board", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Start watching
      const watchPromise = board.watch("alice");

      // Simulate a change after a short delay
      setTimeout(async () => {
        await board.flip("bob", 0, 0);
      }, 10);

      // Watch should resolve after the flip
      const state = await watchPromise;
      assert(state.includes("up"), "Board should show the flipped card");
    });

    it("notifies watchers on card flip", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      const watchPromise = board.watch("observer");

      // Alice flips a card
      setTimeout(async () => {
        await board.flip("alice", 1, 1);
      }, 10);

      const state = await watchPromise;
      assert(state.length > 0, "Watch should return board state after change");
    });

    it("notifies watchers on card removal", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Set up a match
      await board.flip("alice", 0, 0); // First card
      await board.flip("alice", 0, 1); // Matching second card

      const watchPromise = board.watch("observer");

      // Next move should remove the matched pair
      setTimeout(async () => {
        await board.flip("alice", 1, 0);
      }, 10);

      const state = await watchPromise;
      assert(
        state.length > 0,
        "Watch should return board state after card removal"
      );
    });

    it("notifies watchers on map transformation", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      const watchPromise = board.watch("observer");

      // Transform all cards
      setTimeout(async () => {
        await board.map("alice", async (card: string) => `new-${card}`);
      }, 10);

      const state = await watchPromise;
      assert(
        state.length > 0,
        "Watch should return board state after transformation"
      );
    });

    it("supports multiple simultaneous watchers", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Multiple players watching
      const watch1 = board.watch("observer1");
      const watch2 = board.watch("observer2");
      const watch3 = board.watch("observer3");

      // Trigger a change
      setTimeout(async () => {
        await board.flip("alice", 0, 0);
      }, 10);

      // All watchers should be notified
      const [state1, state2, state3] = await Promise.all([
        watch1,
        watch2,
        watch3,
      ]);

      assert(state1.length > 0, "Observer 1 should get board state");
      assert(state2.length > 0, "Observer 2 should get board state");
      assert(state3.length > 0, "Observer 3 should get board state");
    });

    it("does not block other operations", async function () {
      const board = await Board.parseFromFile("boards/perfect.txt");

      // Start watching (will wait indefinitely until a change)
      const watchPromise = board.watch("observer");

      // Other operations should still work
      const lookState = board.look("alice");
      assert(lookState.length > 0, "Look should work while watch is waiting");

      // Trigger the watch to complete
      setTimeout(async () => {
        await board.flip("bob", 0, 0);
      }, 10);

      await watchPromise;
    });
  });
});

/**
 * Example test case that uses async/await to test an asynchronous function.
 * Feel free to delete these example tests.
 */
describe("async test cases", function () {
  it("reads a file asynchronously", async function () {
    const fileContents = (
      await fs.promises.readFile("boards/ab.txt")
    ).toString();
    assert(fileContents.startsWith("5x5"));
  });
});
