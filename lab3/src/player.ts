/**
 * Mutable ADT representing a player in the Memory Scramble game.
 * 
 * A player is identified by a unique string ID and tracks their game statistics
 * including flip attempts, as well as their current game state.
 */

export class Player {
    private readonly id: string;
    private flips: number;
    private firstCard: { row: number; col: number } | null;
    private secondCard: { row: number; col: number } | null;
    
      // Rep invariant:
    //   - id is a nonempty string with no whitespace
    //   - flips >= 0, is an integer
    //   - firstCard is null or an object with integer row and col
    //   - secondCard is null or an object with integer row and col
    //
    // Abstraction function:
    //   AF(id, flips, firstCard, secondCard) =
    //     A player with unique identifier 'id',
    //     who has performed 'flips' flip attempts,
    //     currently controlling firstCard (if not null) and secondCard (if not null)
    //
    // Safety from rep exposure:
    //   - All fields are private
    //   - id is readonly; id is a string (immutable)
    //   - flips is a number (immutable primitive)
    //   - All observers return immutable primitives or null
    //   - firstCard and secondCard getters return copies of the objects
    //   - No mutable objects are shared with clients


    /**
     * Create a new player.
     * 
     * @param playerId unique player identifier (nonempty string, no whitespace)     
     * @throws Error if playerId is empty, contains whitespace
     */
    public constructor(playerId: string) {
        this.id = playerId;
        this.flips = 0;
        this.firstCard = null;
        this.secondCard = null;
        this.checkRep();
    }

    /**
     * Get the player's unique identifier.
     * @returns the player's id
     */
    public getId(): string { return this.id; }



    /**
     * Record a flip attempt by this player.
     * Increments the flip count by 1.
     */
    public recordFlip(): void {
        this.flips += 1;
        this.checkRep();
    }


    /**
     * Get the number of flip attempts made by this player.
     * @returns number of flips (>= 0)
     */
    public getFlips(): number { return this.flips; }

    /**
     * Get the first card position controlled by this player.
     * @returns copy of first card position or null if none
     */
    public getFirstCard(): { row: number; col: number } | null {
        return this.firstCard ? { ...this.firstCard } : null;
    }

    /**
     * Set the first card position for this player.
     * @param position card position or null to clear
     */
    public setFirstCard(position: { row: number; col: number } | null): void {
        this.firstCard = position;
        this.checkRep();
    }

    /**
     * Get the second card position controlled by this player.
     * @returns copy of second card position or null if none
     */
    public getSecondCard(): { row: number; col: number } | null {
        return this.secondCard ? { ...this.secondCard } : null;
    }

    /**
     * Set the second card position for this player.
     * @param position card position or null to clear
     */
    public setSecondCard(position: { row: number; col: number } | null): void {
        this.secondCard = position;
        this.checkRep();
    }

    /**
     * Clear both first and second card positions.
     */
    public clearCards(): void {
        this.firstCard = null;
        this.secondCard = null;
        this.checkRep();
    }

    /**
     * Check if this is a first card flip (no first card set yet).
     * @returns true if no first card is set
     */
    public isFirstCardFlip(): boolean {
        return this.firstCard === null;
    }

    /**
     * Get a string representation for debugging.
     * @returns string describing this player and their statistics
     */
    public toString(): string {
        return `Player(${this.id}, flips=${this.flips})`;
    }

    /**
     * Assert the representation invariant.
     * @throws Error if rep invariant is violated
     */
    private checkRep(): void {
        if (typeof this.id !== 'string' || this.id.length === 0 || /\s/.test(this.id)) {
            throw new Error(`invalid id: ${this.id}`);
        }
        if (!Number.isInteger(this.flips) || this.flips < 0) {
            throw new Error(`invalid flips: ${this.flips}`);
        }
        if (this.firstCard !== null) {
            if (!Number.isInteger(this.firstCard.row) || !Number.isInteger(this.firstCard.col)) {
                throw new Error(`invalid firstCard position`);
            }
        }
        if (this.secondCard !== null) {
            if (!Number.isInteger(this.secondCard.row) || !Number.isInteger(this.secondCard.col)) {
                throw new Error(`invalid secondCard position`);
            }
        }
    }
}
