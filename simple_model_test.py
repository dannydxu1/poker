import re
import numpy as np
import random
import tensorflow as tf
from treys import Deck, Evaluator, Card
from pypokerengine.api.game import setup_config, start_poker
from pypokerengine.players import BasePokerPlayer
from ppe_bot import to_treys
# —————————————————————————————
# 1) Load your trained model
# —————————————————————————————
model = tf.keras.models.load_model('poker_bot.h5')

# —————————————————————————————
# 2) State-encoding helpers
# —————————————————————————————
RANKS = '23456789TJQKA'
SUITS = 'HDCS'
ALL_CARDS = [s + r for r in RANKS for s in SUITS]
card_to_idx = {c: i for i, c in enumerate(ALL_CARDS)}

bot_stats = {"fold": 0, "call": 0, "raise": 0}

def cards_to_onehot(cards):
    vec = np.zeros(len(ALL_CARDS), dtype=np.float32)
    for c in cards:
        vec[card_to_idx[c]] = 1.0
    return vec

def encode_state(hole, board, pot, hero_stack, opp_stack):
    # hole & board one-hots, plus numeric feats
    hole_oh = cards_to_onehot(hole)
    board_padded = board + ['']*(5-len(board))
    board_oh = cards_to_onehot([c for c in board_padded if c])
    feats = np.array([pot, hero_stack, opp_stack, len(board)], dtype=np.float32)
    return np.concatenate([hole_oh, board_oh, feats])

# —————————————————————————————
# 3) ModelPlayer wrapper
# —————————————————————————————
class ModelPlayer(BasePokerPlayer):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def declare_action(self, valid_actions, hole_card, round_state):
        print("Hero cards")
        Card.print_pretty_cards(to_treys(hole_card))
        # build the same state vector you trained on
        pot = round_state['pot']['main']['amount']
        hero_contrib = 0 # TODO: Fix this
        # opponent stack ≈ total pot + blinds*2 – hero_contrib
        opp_stack = pot + 5*2 - hero_contrib
        community_cards = round_state['community_card']
        state = encode_state(hole_card, community_cards, pot, hero_contrib, opp_stack)
        probs = self.model.predict(state[np.newaxis])[0]
        print(probs)
        # target_action = ['fold','call','raise'][np.argmax(probs)]
        target_action = np.random.choice(['fold', 'call', 'raise'], p=probs)
        # pick the matching valid action
        for act in valid_actions:
            if act['action'] == target_action:
                bot_stats[target_action] += 1
                if target_action == "raise":
                    min_raise, max_raise = act['amount']["min"],  act['amount']["max"]
                    amount = random.randint(min_raise, min(max_raise, 3*pot)) # no egregious raise sizing
                    print(act['action'], act['amount'])
                    return act['action'], amount
                print(act['action'], act['amount'])
                return act['action'], act['amount']
        # fallback: call
        return valid_actions[1]['amount']

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

# —————————————————————————————
# 4) Run a heads-up match
# —————————————————————————————
class FishPlayer(BasePokerPlayer):  # Do not forget to make parent class as "BasePokerPlayer"
    #  we define the logic to make an action through this method. (so this method would be the core of your AI)
    def declare_action(self, valid_actions, hole_card, round_state):
        # valid_actions format => [raise_action_info, call_action_info, fold_action_info]
        print("Villain cards")
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


if __name__ == "__main__":
    config = setup_config(
        max_round=200,            # number of hands
        initial_stack=1000,
        small_blind_amount=5,
        ante=0
    )
    config.register_player(name="Hero (AI)", algorithm=ModelPlayer(model))
    config.register_player(name="Villain (RNGesus)", algorithm=FishPlayer())
    result = start_poker(config, verbose=1)
    print("Match result:", result)
    print("Bot stats:", bot_stats)
