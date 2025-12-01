/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

// import assert from 'node:assert';
import { Board } from "./board.js";

/**
 * Example code for simulating a game.
 *
 * PS4 instructions: you may use, modify, or remove this file,
 *   completing it is recommended but not required.
 *
 * @throws Error if an error occurs reading or parsing the board
 */
async function simulationMain(): Promise<void> {
  const filename = "boards/ab.txt";
  const board: Board = await Board.parseFromFile(filename);
  const size = 5;
  const players = 4; // 4 concurrent players as per requirements
  const tries = 100; // 100 moves each as per requirements
  const minDelayMilliseconds = 0.1; // Minimum timeout 0.1ms
  const maxDelayMilliseconds = 2; // Maximum timeout 2ms

  console.log(
    `Starting simulation with ${players} players, ${tries} tries each`
  );
  console.log(`Board size: ${size}x${size}`);
  console.log(
    `Timeouts: ${minDelayMilliseconds}ms - ${maxDelayMilliseconds}ms`
  );
  console.log("Testing concurrent gameplay without crashes...\n");

  // start up one or more players as concurrent asynchronous function calls
  const playerPromises: Array<Promise<void>> = [];
  for (let ii = 0; ii < players; ++ii) {
    playerPromises.push(player(ii));
  }
  // wait for all the players to finish (unless one throws an exception)
  await Promise.all(playerPromises);

  console.log("\nSimulation completed successfully!");
  console.log("All players finished without crashes.");

  /** @param playerNumber player to simulate */
  async function player(playerNumber: number): Promise<void> {
    const playerId = `player${playerNumber}`;
    let successfulMoves = 0;
    let failedMoves = 0;

    for (let jj = 0; jj < tries; ++jj) {
      try {
        await timeout(
          minDelayMilliseconds +
            Math.random() * (maxDelayMilliseconds - minDelayMilliseconds)
        );
        // Try to flip over a first card at random position
        const firstRow = randomInt(size);
        const firstCol = randomInt(size);
        await board.flip(playerId, firstRow, firstCol);

        await timeout(
          minDelayMilliseconds +
            Math.random() * (maxDelayMilliseconds - minDelayMilliseconds)
        );
        // Try to flip over a second card at random position
        const secondRow = randomInt(size);
        const secondCol = randomInt(size);
        await board.flip(playerId, secondRow, secondCol);

        successfulMoves++;
      } catch (err) {
        failedMoves++;
        // Errors are expected (e.g., flipping empty spots), just continue
      }
    }

    console.log(
      `${playerId}: ${successfulMoves} successful moves, ${failedMoves} failed attempts`
    );
  }
}

/**
 * Random positive integer generator
 *
 * @param max a positive integer which is the upper bound of the generated number
 * @returns a random integer >= 0 and < max
 */
function randomInt(max: number): number {
  return Math.floor(Math.random() * max);
}

/**
 * @param milliseconds duration to wait
 * @returns a promise that fulfills no less than `milliseconds` after timeout() was called
 */
async function timeout(milliseconds: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, milliseconds);
  return promise;
}

void simulationMain();
