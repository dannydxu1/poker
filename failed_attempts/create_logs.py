import os
import json
import pickle
import random

from openCFR.games.sample_games import TexasHoldEm
from openCFR.minimizers import CFRPlus
from openCFR.minimizers import VanillaCFR
from openCFR.Trainer import Trainer

from pypokerengine.api.game import setup_config, start_poker
from pypokerengine.players import BasePokerPlayer

from openCFR.games.sample_games import TexasHoldEm
from importlib import resources

GAME = TexasHoldEm(small_blind=2, big_blind=4, starting_stack=50)
with resources.files('openCFR').joinpath('pretrained/TexasHoldEm_final.pickle').open('rb') as f:
    INFOSETS = pickle.load(f) 
print(f"Loaded {len(INFOSETS):,}")

# -------------------------------------------------------------------------
# 2) History builder: map PyPokerEngine state → openCFR infoset key
# --------------------------    -----------------------------------------------
def build_history_from_round_state(game, hole_cards, round_state):
    history = []
    street = round_state['street']

    # 2a) Hero's private chance events: bucket the hole cards
    for card in hole_cards:
        bucket = game.bucket_hole_cards(0, card)
        history.append(('r', str(bucket)))

    # 2b) Community chance events when they appear
    if street == 'flop':
        cards = round_state['community_card'][0:3]
    elif street == 'turn':
        cards = [round_state['community_card'][3]]
    elif street == 'river':
        cards = [round_state['community_card'][4]]
    else:
        cards = []
    for c in cards:
        b = game.bucket_public_card(c)
        history.append(('r', str(b)))

    # 2c) Player actions this street
    actions = round_state['action_histories'][street]
    for act in actions:
        # map UUID to seat index (0 or 1)
        pid = 0 if act['uuid'] == round_state['seats'][0]['uuid'] else 1
        name = act['action'].lower()
        if name not in game.action_map:
            name = 'raise'
        aidx = game.action_map.index(name)
        history.append((pid, aidx))

    return history

# -------------------------------------------------------------------------
# 3) LoggerPlayer: logs state + CFR policy at each hero decision
# -------------------------------------------------------------------------
class CFRLogger(BasePokerPlayer):
    def __init__(self, logger, seat_id):
        self.logger = logger
        self.seat_id = seat_id
        self.hole_cards = []

    def receive_round_start_message(self, round_count, hole_card, seats):
        # store hero hole cards
        self.hole_cards = hole_card

    def declare_action(self, valid_actions, hole_cards, round_state):
        # build imperfect‐info history
        history = build_history_from_round_state(GAME,
                                                 self.hole_cards,
                                                 round_state)
        key = GAME.get_infoset_key(history)
        info = INFOSETS.get(key)
        # if key missing, fall back to uniform random
        if info is None:
            teacher = {a: 1/len(valid_actions) for a in valid_actions}
        else:
            strat = info.get_average_strategy()
            teacher = {a: strat[i]
                       for i,a in enumerate(GAME.action_map)
                       if a in valid_actions}
            # normalize
            s = sum(teacher.values())
            teacher = {a: p/s for a,p in teacher.items()}

        # log the state and teacher policy
        public = {
            'community_cards': round_state['community_card'],
            'pot':              round_state['pot']['main']['amount'],
            'street':           round_state['street'],
            'sb_pos':           round_state['small_blind_pos'],
            'bb_pos':           round_state['big_blind_pos'],
            'stacks':           [s['stack'] for s in round_state['seats']]
        }
        private = {
            'hole_cards': self.hole_cards,
            'stack':      round_state['seats'][self.seat_id]['stack']
        }
        record = {
            'public_state':  public,
            'private_state': private,
            'action_probs':  teacher
        }
        self.logger.write(json.dumps(record) + "\n")
        self.logger.flush()

        # sample an action just to continue the game
        choice = random.choices(list(teacher.keys()),
                                 weights=list(teacher.values()))[0]
        return choice, 0

    # no-op handlers
    def receive_game_start_message(self, game_info): pass
    def receive_street_start_message(self, street, round_state): pass
    def receive_game_update_message(self, action, round_state): pass
    def receive_round_result_message(self, winners, hand_info, round_state): pass

# -------------------------------------------------------------------------
# 4) Main: self-play with CFRLogger and write JSONL
# -------------------------------------------------------------------------
def main(log_path, num_hands=100000):
    with open(log_path, 'w') as logger:
        config = setup_config(max_round=4,
                              initial_stack=1000,
                              small_blind_amount=5)
        config.register_player(name="p0",
                               algorithm=CFRLogger(logger, 0))
        config.register_player(name="p1",
                               algorithm=CFRLogger(logger, 1))

        hands = 0
        while hands < num_hands:
            start_poker(config, verbose=0)
            hands += 1
            if hands % 5000 == 0:
                print(f"Logged {hands} hands")

if __name__ == '__main__':
    main("cfr_selfplay.jsonl", num_hands=100000)
