"""
Minimal six-max no-limit Hold'em simulator and baseline bot using only Treys for hand evaluation.
"""
import random
from treys import Deck, Evaluator, Card
from pypokerengine.players import BasePokerPlayer
from pypokerengine.api.game import setup_config, start_poker

# Game constants
SMALL_BLIND = 5
BIG_BLIND = 10
INITIAL_STACK = 1000
NUM_OPPONENTS = 1
MC_SIMS = 500
NUM_PLAYERS = NUM_OPPONENTS + 1

class FishPlayer(BasePokerPlayer):  # Do not forget to make parent class as "BasePokerPlayer"
    #  we define the logic to make an action through this method. (so this method would be the core of your AI)
    def declare_action(self, valid_actions, hole_card, round_state):
        # valid_actions format => [raise_action_info, call_action_info, fold_action_info]
        print("fish cards")
        Card.print_pretty_cards(to_treys(hole_card))
        decision = random.randint(0,2)
        action, amount = valid_actions[decision]["action"], valid_actions[decision]["amount"]
        pot_size = round_state['pot']['main']['amount']
        if action == "raise":
            min_raise, max_raise = amount["min"],  amount["max"]
            amount = random.randint(min_raise, min(max_raise, 3*pot_size)) # no egregious raise sizing
        return action, amount   # action returned here is sent to the poker engine

    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        pass

    def receive_round_result_message(self, winners, hand_info, round_state):
        pass

class MCPlayer(BasePokerPlayer):  # Do not forget to make parent class as "BasePokerPlayer"
    #  we define the logic to make an action through this method. (so this method would be the core of your AI)
    def declare_action(self, valid_actions, hole_card, round_state):
        # valid_actions format => [raise_action_info, call_action_info, fold_action_info]
        call_action_info = valid_actions[1]
        # action, amount = call_action_info["action"], call_action_info["amount"]
        stack_size = round_state['seats'][1]['stack']
        action, amount = self.decide(valid_actions, to_treys(hole_card), to_treys(round_state['community_card']), round_state['pot']['main']['amount'], call_action_info["amount"], stack_size)
        return action, amount   # action returned here is sent to the poker engine

    def receive_game_start_message(self, game_info):
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        pass

    def receive_round_result_message(self, winners, hand_info, round_state):
        pass

    def decide(self, valid_actions, hole, board, pot, to_call, stack_size):
        print("hero cards")
        Card.print_pretty_cards(hole)
        Card.print_pretty_cards(board)
    
        eq = self.estimate_equity(hole, board)
        ev_fold = 0

        pot_odds = to_call / pot
        if to_call == BIG_BLIND and eq < 0.40:
                print(f"open folding due  to pot odds: {eq:.2f} chance of winning with {pot_odds:.2f} odds")
                return 'fold', 0
        if to_call > BIG_BLIND and eq < pot_odds*0.9:
            print(f"folding due to pot odds: {eq:.2f} chance of winning with {pot_odds:.2f} odds")
            return 'fold', 0
    
        winning_odds, losing_odds = eq, 1 - eq
        ev_call = winning_odds * (pot + to_call) - losing_odds * to_call

        X = eq * pot / losing_odds
        raise_amt = round(min(stack_size, to_call + X))
        ev_raise = winning_odds * (pot + raise_amt) - losing_odds * raise_amt

        print(f"  equity = {eq:.2f}, ev_call = {ev_call:.2f}, to_call = {to_call}, ev_raise = {ev_raise:.2f}, raise_amt = {raise_amt}")

        if ev_raise >= ev_call and ev_raise >= ev_fold:
            return 'raise', raise_amt
        if ev_call >= ev_fold and to_call >= 0:
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
            evaluator = Evaluator()
            future = deck.draw(5 - len(board))
            future_strs = [Card.int_to_str(c) for c in future]
            full_board = board + future
            my_score = evaluator.evaluate(hole, full_board)
            opp_scores = [evaluator.evaluate(h, full_board) for h in opps]
            best_opp = min(opp_scores)
            if my_score < best_opp:
                wins += 1
            elif my_score == best_opp:
                ties += 1
        return (wins + ties / 2) / MC_SIMS

def to_treys(cards):
    ret = []
    for c in cards:
        rank = c[1] 
        suit = c[0].lower()
        treys_card = Card.new(rank + suit)
        ret.append(treys_card)
    return ret

if __name__ == '__main__':
    config = setup_config(max_round=10, initial_stack=INITIAL_STACK, small_blind_amount=SMALL_BLIND)
    config.register_player(name="FishPlayer", algorithm=FishPlayer())
    config.register_player(name="MCPlayer", algorithm=MCPlayer())
    game_result = start_poker(config)