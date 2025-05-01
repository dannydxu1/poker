from pypokerengine.players import BasePokerPlayer
import random

class RandomPlayer(BasePokerPlayer):
    """
    Randomly selects a legal action and returns the correct amount format.
    """
    def __init__(self):
        super().__init__()

    def declare_action(self, valid_actions, hole_cards, round_state):
        choice = random.choice(valid_actions)
        action = choice['action']
        amt_info = choice['amount']
        # Handle both int (call/fold) and dict (raise) amount formats
        if isinstance(amt_info, dict):
            amt = amt_info.get('min', 0)
        else:
            amt = amt_info
        return action, amt

    # No-op callbacks
    def receive_game_start_message(self, game_info): pass
    def receive_round_start_message(self, round_count, hole_cards, seats): pass
    def receive_street_start_message(self, street, round_state): pass
    def receive_game_update_message(self, action, round_state): pass
    def receive_round_result_message(self, winners, hand_info, round_state): pass
