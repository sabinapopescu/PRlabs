# LAB 3 PR: Memory Scramble
During this laboratory work I developed a networked multiplayer version of Memory Scramble, the game in which you turn over face-down cards and try to find matching pairs. My version has players turning over cards simultaneously, rather than taking turns.

## Contents of Directory
* I have multiple directories in the root. The *boards* directory contains game board configuration files (ab.txt, perfect.txt, zoom.txt) that define different card layouts. *src* contains the TypeScript source files including the core game logic (board.ts, player.ts, server.ts, commands.ts, simulation.ts). test contains unit tests (board.test.ts) for testing the game components. *public* contains  web assets served to clients. *doc* contains documentation resources organized into subdirectories using *TypeDoc*.
* In this project, the *Dockerfile* defines how the game server environment is built, including TypeScript compilation, and all necessary dependencies to run the Memory Scramble server inside a container. The docker-compose.yml file orchestrates the container, mapping port 8080 for HTTP access and specifying which board file to use when starting the server.

![](images_report/image.png)

## Dockerfile
The *Dockerfile* sets up the environment, copies the package.json files and installs all npm dependencies, then copies the entire project source code into the container's /app directory. It compiles the TypeScript source files into JavaScript using npm run compile, exposes port 8080 for HTTP access, and starts the Memory Scramble server with the perfect.txt board configuration file.

```dockerfile
FROM node:22.12
WORKDIR /app
COPY package*.json ./

RUN npm install
COPY . .
RUN npm run compile
EXPOSE 8080
CMD ["node", "--require", "source-map-support/register", "dist/src/server.js", "8080", "boards/perfect.txt"]
```

## Docker compose
This *docker-compose.yml* file defines a single service called game-server that builds the containerized environment, maps port 8080 for HTTP access to the Memory Scramble game server, and runs the compiled TypeScript server with the perfect.txt board configuration file.

```dockerfile
services:
  game-server:
    build: .
    ports:
      - "8080:8080"
    command: ["node", "--require", "source-map-support/register", "dist/src/server.js", "8080", "boards/perfect.txt"]
```

## Running the project
We can run the project locally using the command:
```
npm start 8080 boards/perfect.txt
```
We can also run it using docker with the following command:
```
docker compose up
```

## Documentation
I wrote documentation using JsDoc and it was generated as an html page using TypeDoc. I generated it using the command:
```
npm run doc
```
We can see the documentation in the following pictures. It contains, classes, functions, parameters and returns of functions. It also has an overview of what each function does.

![](images_report/image-1.png)

![](images_report/image-2.png)

![](images_report/image-3.png)

## Testing
I wrote tests for all rules and parsing of the board as well. Tests can be run with the following command:
```
npm run test
```

They all successfully run, as can be seen in the following picture:

![](images_report/image-4.png)

## Simulation
I have both simple polling mode simulation with one watcher to state changes and a simulation with players that are only in watch mode.
To run the basic polling simulation, we run:
```
npm run simulation
```

![](images_report/image-5.png)

![](images_report/image-6.png)

Every operation done by each player and every operation observed by board and watcher is logged to test if rules are applied correctly.

To start the simulation with only watchers, we run:

```
npm run simulation watch
```

And we see actions from players as well as logs that prove that other players detected that move as well.

![](images_report/image-7.png)

## Play by rules

First card: a player tries to turn over a first card by identifying a space on the board…

### 1-A: If there is no card there (the player identified an empty space, perhaps because the card was just removed by another player), the operation fails.
If I try to click on a card that was removed after a match, i will get a error pop up and i won't be able to take control of that space.

![](images_report/image-11.png)

### 1-B: If the card is face down, it turns face up (all players can now see it) and the player controls that card.
I flipped a card and it can be seen both on my screen and the other player's screen.

![](images_report/image-8.png)

### 1-C: If the card is already face up, but not controlled by another player, then it remains face up, and the player controls the card.
No one had control over the rainbow card and it was face up, so I clicked on it and took control.

![](images_report/image-9.png)

![](images_report/image-10.png)

### 1-D: And if the card is face up and controlled by another player, the operation waits. The player will contend with other players to take control of the card at the next opportunity.
If I click on a card controlled by someone else, it will turn green and I will wait till it is free.

![](images_report/image-12.png)

Second card: once a player controls their first card, they can try to turn over a second card…

### 2-A: If there is no card there, the operation fails. The player also relinquishes control of their first card (but it remains face up for now).
I tried to take control of empty space as second card and I relinquished control of the first card.

![](images_report/image-13.png)

![](images_report/image-14.png)

### 2-B: If the card is face up and controlled by a player (another player or themselves), the operation fails. To avoid deadlocks, the operation does not wait. The player also relinquishes control of their first card (but it remains face up for now).
 When I try to choose as second card a already controlled card, I lose control of first card and I get an error.

![](images_report/image-15.png)

![](images_report/image-16.png)

If the card is face down, or if the card is face up but not controlled by a player, then:

### 2-C: If it is face down, it turns face up.

![](images_report/image-17.png)

### 2-D: If the two cards are the same, that’s a successful match! The player keeps control of both cards (and they remain face up on the board for now).

![](images_report/image-17.png)


### 2-E: If they are not the same, the player relinquishes control of both cards (again, they remain face up for now).

I tried to flip a rainbow and then I flipped an unicorn. They are not a match, so I lost control over them.

![](images_report/image-19.png)

![](images_report/image-20.png)

After trying to turn over a second card, successfully or not, the player will try again to turn over a first card. When they do that, before following the rules above, they finish their previous play:

### 3-A: If they had turned over a matching pair, they control both cards. Now, those cards are removed from the board, and they relinquish control of them. Score-keeping is not specified as part of the game.

The removed cards are from matching pairs:

![](images_report/image-18.png)

### 3-B: Otherwise, they had turned over one or two non-matching cards, and relinquished control but left them face up on the board. Now, for each of those card(s), if the card is still on the board, currently face up, and currently not controlled by another player, the card is turned face down.

 After losing relinquishing control of pair, they are turned down when I make next move.

![](images_report/image-21.png)

![](images_report/image-22.png)


### Map
I mapped the unicorns to lolipops succesfully:

![](images_report/image-23.png)