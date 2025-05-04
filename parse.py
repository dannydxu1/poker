import re
import ast
import os
import json
import numpy as np
from tqdm import tqdm 

RANKS = '23456789TJQKA'
SUITS = 'hdcs'
ALL_CARDS = [r+s for r in RANKS for s in SUITS]
card_to_idx = {c:i for i,c in enumerate(ALL_CARDS)}

def cards_to_onehot(cards):
    vec = np.zeros(len(ALL_CARDS), dtype=np.float32)
    for c in cards:
        vec[card_to_idx[c]] = 1.0
    return vec

def encode_decision(dec):
    # allow missing hole → zero vector
    hole_oh = cards_to_onehot(dec.get('hole', []))
    # board one-hot (pad missing)
    board_cards = dec['board'] + ['']*(5-len(dec['board']))
    board_oh = cards_to_onehot([c for c in board_cards if c])
    # numeric features
    feats = np.array([
        dec['pot'],
        dec['hero_stack'],
        dec['opp_stack'],
        len(dec['board']),
    ], dtype=np.float32)
    state = np.concatenate([hole_oh, board_oh, feats])
    action_map = {'fold':0, 'call':1, 'raise':2}
    label = action_map[dec['action']]
    return state, label

def section_to_decisions(sec, hero_seat=1):
    blinds = sec['blinds']
    antes  = sec['antes']
    stacks = sec['starting_stacks']
    seats  = sec['seats']
    pot    = sum(antes) + sum(blinds)
    hero_idx = seats.index(hero_seat)
    hero_stack = stacks[hero_idx]
    opp_stack  = sum(stacks) - hero_stack

    board = []
    decisions = []
    # very basic to_call logic: track last_raise
    last_raise = max(blinds)
    for act in sec['actions']:
        parts = act.split()
        tag = parts[1]
        if tag == "sm":
            continue

        if tag == 'db':  # deal board
            # e.g. parts[2] = '7s9hAc'
            cards = re.findall(r'.{2}', parts[2])
            board += cards
            continue

        # only record when hero acts
        if parts[0] == f'p{hero_seat}':
            if tag == 'f':
                action, amt = 'fold', 0
            elif tag in ('c','cc'):
                action, amt = 'call', last_raise
            else:  # bet/raise
                action, amt = 'raise', int(float(parts[2]))
                last_raise = amt
            decisions.append({
                'hole': [],            # unknown in this format
                'board': board.copy(),
                'pot': pot,
                'hero_stack': hero_stack,
                'opp_stack': opp_stack,
                'legal_actions': ['fold','call','raise'],
                'action': action,
                'amount': amt,
            })

        # update pot & stacks
        if parts[0].startswith('p'):
            actor = int(parts[0][1:])
            if tag in ('c','cc'):
                delta = last_raise
            elif tag in ('br','cbr'):
                delta = int(float(parts[2]))
                last_raise = delta
            else:
                delta = 0
            pot += delta
            if actor == hero_seat:
                hero_stack -= delta
            else:
                opp_stack  -= delta

    return decisions

def prune_section(sec):
    return {
        'blinds':       sec['blinds_or_straddles'],
        'antes':        sec['antes'],
        'starting_stacks': sec['starting_stacks'],
        'actions':      sec['actions'],
        'seats':        sec['seats'],
    }

def parse_config_phhs_file(path):
    """
    Reads a file with sections [1], [2], … each containing lines like
      key = value
    where value may be a Python literal (strings, lists, numbers)
    or JS‐style booleans (true/false).
    Returns a list of dicts, one per section.
    """
    text = open(path, 'r').read()
    # NEW: convert JS‐style booleans into Python
    text = text.replace('false','False').replace('true','True')
    # NEW: split on lines that look exactly like “[digit]”
    parts   = re.split(r'(?m)^\[\d+\]\s*$', text)
    headers = re.findall(r'(?m)^\[(\d+)\]\s*$', text)
    sections = []
    for idx, body in zip(headers, parts[1:]):
        sec = {}
        for line in body.splitlines():
            line = line.strip()
            if not line or '=' not in line:
                continue
            key, val_str = map(str.strip, line.split('=', 1))
            try:
                val = ast.literal_eval(val_str)
            except Exception:
                val = val_str.strip("'\"")
            sec[key] = val
        sections.append(prune_section(sec))
    return sections

if __name__ == "__main__":
    repo_dir = "/Users/dannyxu/code/phh-dataset/data/handhq/PTY-2009-07-01_2009-07-23_1000NLH_OBFU/10"
    all_sections = []
    for fn in tqdm(os.listdir(repo_dir), desc="Processing files"):
        if fn.endswith('.phhs'):
            path = os.path.join(repo_dir, fn)
            all_sections.extend(parse_config_phhs_file(path))


    all_decisions = []
    for sec in tqdm(all_sections, desc="Processing sections"):
        for hero_seat_num in sec['seats']:
            all_decisions += section_to_decisions(sec, hero_seat=hero_seat_num)

    X_list, y_list = [], []
    for dec in all_decisions:
        x, y = encode_decision(dec)
        X_list.append(x)
        y_list.append(y)

    X = np.stack(X_list)      # shape (N, D)
    y = np.array(y_list)      # shape (N,)

    print("Built dataset:", X.shape, y.shape)
    # → now you can split and wrap in a DataLoader for training your PyTorch model