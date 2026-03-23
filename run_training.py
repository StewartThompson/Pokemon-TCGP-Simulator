#!/usr/bin/env python3
"""Run training benchmark with progress output."""

import sys
import os

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

from ptcgp.engine.cards import load_all_cards
from ptcgp.data.decks.sample_decks import get_deck
from ptcgp.training.train import train_agent, evaluate_model

load_all_cards()
d1 = get_deck('grass')
d2 = get_deck('fire')

print('=' * 60, flush=True)
print('TRAINING: 20k steps with curriculum learning', flush=True)
print('=' * 60, flush=True)

model = train_agent(
    d1['cards'], d2['cards'],
    d1['energy_types'], d2['energy_types'],
    total_timesteps=20_000,
    n_envs=4,
    curriculum=True,
    save_path='models/benchmark_20k',
    verbose=1,
)

print(flush=True)
print('=' * 60, flush=True)
print('FINAL EVALUATION', flush=True)
print('=' * 60, flush=True)

results_random = evaluate_model(
    model, d1['cards'], d2['cards'],
    d1['energy_types'], d2['energy_types'],
    opponent='random', n_games=100,
)
print(f'vs Random:    {results_random["win_rate"]:.1%} ({results_random["wins"]}W/{results_random["losses"]}L/{results_random["draws"]}D)', flush=True)

results_heuristic = evaluate_model(
    model, d1['cards'], d2['cards'],
    d1['energy_types'], d2['energy_types'],
    opponent='heuristic', n_games=100,
)
print(f'vs Heuristic: {results_heuristic["win_rate"]:.1%} ({results_heuristic["wins"]}W/{results_heuristic["losses"]}L/{results_heuristic["draws"]}D)', flush=True)

print('\nDone!', flush=True)
