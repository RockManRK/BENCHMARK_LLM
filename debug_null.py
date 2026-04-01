#!/usr/bin/env python3
"""Debug script for null normalization."""

from src.cli.bcllm_experiment import create_parser
from src.core.argv_utils import parse_args_normalized, normalize_nulls
from src.core.null_semantics import FORCE_SYSTEM_DEFAULT

parser = create_parser()

# Test without normalization - 'system-default' should be normalized
args_raw = parser.parse_args(['--create-experiment', 'test', '--seed', 'system-default'])
print(f'RAW: args.seed = {repr(args_raw.seed)}')

# Test with normalization - should convert 'system-default' to FORCE_SYSTEM_DEFAULT
args_norm = parse_args_normalized(parser, ['--create-experiment', 'test', '--seed', 'system-default'])
print(f'NORM: args.seed = {repr(args_norm.seed)}')
print(f'Is FORCE_SYSTEM_DEFAULT: {args_norm.seed is FORCE_SYSTEM_DEFAULT}')

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
