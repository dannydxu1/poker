"""
Minimal six-max no-limit Hold'em simulator and baseline bot using only Treys for hand evaluation.
"""
import random
from treys import Deck, Evaluator, Card

# Game constants
SMALL_BLIND = 5
BIG_BLIND = 10
INITIAL_STACK = 1000
NUM_OPPONENTS = 5
MC_SIMS = 500
NUM_PLAYERS = NUM_OPPONENTS + 1

class Player:
    def __init__(self, name, stack=INITIAL_STACK):
        self.name = name
        self.stack = stack
        self.hole = []
        self.in_hand = True

    def reset_hand(self):
        self.hole = []
        self.in_hand = True

    def post_blind(self, amount):
        bet = min(self.stack, amount)
        self.stack -= bet
        return bet

    def decide(self, valid_actions, hole, board, pot, to_call):
        raise NotImplementedError

class RandomPlayer(Player):
    def decide(self, valid_actions, hole, board, pot, to_call):
        action = random.choice(valid_actions)
        if action == 'fold': return 'fold', 0
        if action == 'call': return 'call', to_call
        # minimal raise = to_call + BIG_BLIND
        raise_amt = min(self.stack, to_call + BIG_BLIND)
        return 'raise', raise_amt

class BaselineBot(Player):
    def __init__(self, name):
        super().__init__(name)
        self.evaluator = Evaluator()

    def decide(self, valid_actions, hole, board, pot, to_call):
        # estimate equity
        eq = self.estimate_equity(hole, board)
        # compute simple EVs
        ev_fold = 0
        ev_call = eq * (pot + to_call) - (1 - eq) * to_call
        raise_amt = min(self.stack, to_call + BIG_BLIND)
        ev_raise = eq * (pot + raise_amt) - (1 - eq) * raise_amt
        # choose best
        if ev_raise >= ev_call and ev_raise >= ev_fold:
            return 'raise', raise_amt
        if ev_call >= ev_fold:
            return 'call', to_call
        return 'fold', 0

    def estimate_equity(self, hole, board):
        wins = ties = 0
        for _ in range(MC_SIMS):
            deck = Deck()
            deck.shuffle()
            # remove known cards
            for c in hole + board:
                deck.cards.remove(c)
            # deal opponents
            opps = [deck.draw(2) for _ in range(NUM_OPPONENTS)]
            # deal remaining community
            future = deck.draw(5 - len(board))
            future_strs = [Card.int_to_str(c) for c in future]
            full_board = board + future
            try:
                my_score = self.evaluator.evaluate(hole, full_board)
            except KeyError as e:
                print("  hole     =", [Card.int_to_str(c) for c in hole])
                print("  full_board =", [Card.int_to_str(c) for c in full_board])
                raise
            opp_scores = [self.evaluator.evaluate(h, full_board) for h in opps]
            best_opp = min(opp_scores)
            if my_score < best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1
        return (wins + ties / 2) / MC_SIMS

class Game:
    def __init__(self, players):
        self.players = players
        self.dealer_idx = 0

    def rotate_dealer(self):
        self.dealer_idx = (self.dealer_idx + 1) % NUM_PLAYERS

    def play_hand(self):
        # reset
        for p in self.players: p.reset_hand()
        deck = Deck()
        deck.shuffle()
        # post blinds
        sb = self.players[(self.dealer_idx + 1) % NUM_PLAYERS].post_blind(SMALL_BLIND)
        bb = self.players[(self.dealer_idx + 2) % NUM_PLAYERS].post_blind(BIG_BLIND)
        pot = sb + bb
        to_call = BIG_BLIND
        # deal hole
        for p in self.players:
            p.hole = deck.draw(2)

        # betting rounds simplified: each active player acts once
        board = []
        for street in ['preflop','flop','turn','river']:
            if street == 'flop': board = deck.draw(3)
            if street == 'turn' : board.append(deck.draw(1)[0])
            if street == 'river': board.append(deck.draw(1)[0])
            for p in self.players:
                if not p.in_hand: continue
                valid = ['fold','call','raise']
                action, amt = p.decide(valid, p.hole, board, pot, to_call)
                if action == 'fold': p.in_hand = False
                else:
                    bet = min(p.stack, amt)
                    p.stack -= bet
                    pot += bet
                    to_call = bet if action == 'raise' else to_call
        # showdown
        remaining = [p for p in self.players if p.in_hand]
        if not remaining:
            return  # everyone folded
        evaluator = Evaluator()
        scores = {p: evaluator.evaluate(p.hole, board) for p in remaining}
        winner = min(scores, key=scores.get)
        winner.stack += pot

    def run(self, num_hands=100):
        for _ in range(num_hands):
            self.play_hand()
            self.rotate_dealer()
        # final stacks
        for p in self.players:
            print(f"{p.name}: {p.stack}")

if __name__ == '__main__':
    # setup players
    bot = BaselineBot('Bot')
    opponents = [RandomPlayer(f'R{i}') for i in range(NUM_OPPONENTS)]
    game = Game([bot] + opponents)
    game.run(num_hands=50)  # simulate 50 hands
