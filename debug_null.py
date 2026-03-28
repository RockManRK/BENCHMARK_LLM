#!/usr/bin/env python3
"""Debug script for null normalization."""

from src.cli.bcllm_experiment import create_parser
from src.core.argv_utils import parse_args_normalized, normalize_nulls

parser = create_parser()

# Test without normalization
args_raw = parser.parse_args(['--create-experiment', 'test', '--seed', 'null'])
print(f'RAW: args.seed = {repr(args_raw.seed)}')

# Test with normalization
args_norm = parse_args_normalized(parser, ['--create-experiment', 'test', '--seed', 'null'])
print(f'NORM: args.seed = {repr(args_norm.seed)}')

# Check parser action for --seed
for action in parser._actions:
    if action.dest == 'seed':
        print(f'ACTION: dest={action.dest}, default={repr(action.default)}, required={action.required}, type={action.type}')
        break

# Test _is_nullable_arg
from src.core.argv_utils import _is_nullable_arg
for action in parser._actions:
    if action.dest == 'seed':
        print(f'_is_nullable_arg: {_is_nullable_arg(action)}')
        break
