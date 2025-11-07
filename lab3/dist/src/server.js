import assert from 'node:assert';
import process from 'node:process';
import express from 'express';
import { StatusCodes } from 'http-status-codes';
import { Board } from './board.js';
import { look, flip, map, watch } from './commands.js';
/**
 * Initialize and start the Memory Scramble HTTP server.
 * Requires command-line arguments: PORT FILENAME
 *
 * @throws Error if arguments are invalid or board file fails to load
 */
async function main() {
    const [portString, filename] = process.argv.slice(2); // skip the first two arguments 
    // (argv[0] is node executable file, argv[1] is this script)
    if (portString === undefined) {
        throw new Error('missing PORT');
    }
    const port = parseInt(portString);
    if (isNaN(port) || port < 0) {
        throw new Error('invalid PORT');
    }
    if (filename === undefined) {
        throw new Error('missing FILENAME');
    }
    const board = await Board.parseFromFile(filename);
    const server = new WebServer(board, port);
    await server.start();
}
/**
 * HTTP server for Memory Scramble game providing REST API endpoints.
 */
class WebServer {
    board;
    requestedPort;
    app;
    server;
    /**
     * Create a new web server for the game.
     *
     * @param board the game board to serve
     * @param requestedPort port number to listen on
     */
    constructor(board, requestedPort) {
        this.board = board;
        this.requestedPort = requestedPort;
        this.app = express();
        this.app.use((request, response, next) => {
            // allow requests from web pages hosted anywhere
            response.set('Access-Control-Allow-Origin', '*');
            next();
        });
        this.app.get('/look/:playerId', async (request, response) => {
            const { playerId } = request.params;
            assert(playerId);
            const boardState = await look(this.board, playerId);
            response
                .status(StatusCodes.OK) // 200
                .type('text')
                .send(boardState);
        });
        this.app.get('/flip/:playerId/:location', async (request, response) => {
            const { playerId, location } = request.params;
            assert(playerId);
            assert(location);
            const [row, column] = location.split(',').map(s => parseInt(s));
            assert(row !== undefined && !isNaN(row));
            assert(column !== undefined && !isNaN(column));
            try {
                const boardState = await flip(this.board, playerId, row, column);
                response
                    .status(StatusCodes.OK) // 200
                    .type('text')
                    .send(boardState);
            }
            catch (err) {
                response
                    .status(StatusCodes.CONFLICT) // 409
                    .type('text')
                    .send(`cannot flip this card: ${err}`);
            }
        });
        this.app.get('/replace/:playerId/:fromCard/:toCard', async (request, response) => {
            const { playerId, fromCard, toCard } = request.params;
            assert(playerId);
            assert(fromCard);
            assert(toCard);
            const boardState = await map(this.board, playerId, async (card) => card === fromCard ? toCard : card);
            response
                .status(StatusCodes.OK) // 200
                .type('text')
                .send(boardState);
        });
        this.app.get('/watch/:playerId', async (request, response) => {
            const { playerId } = request.params;
            assert(playerId);
            const boardState = await watch(this.board, playerId);
            response
                .status(StatusCodes.OK) // 200
                .type('text')
                .send(boardState);
        });
        this.app.use(express.static('public/'));
    }
    /**
     * Begin listening for HTTP requests.
     *
     * @returns promise that resolves when server is ready
     */
    start() {
        const { promise, resolve } = Promise.withResolvers();
        this.server = this.app.listen(this.requestedPort);
        this.server.on('listening', () => {
            console.log(`server now listening at http://localhost:${this.port}`);
            resolve();
        });
        return promise;
    }
    /**
     * Get the actual port the server is listening on.
     *
     * @returns port number
     * @throws Error if server is not listening
     */
    get port() {
        const address = this.server?.address() ?? 'not connected';
        if (typeof (address) === 'string') {
            throw new Error('server is not listening at a port');
        }
        return address.port;
    }
    /**
     * Stop the server and close all connections.
     */
    stop() {
        this.server?.close();
        console.log('server stopped');
    }
}
await main();
//# sourceMappingURL=server.js.map