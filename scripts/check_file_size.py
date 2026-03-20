#!/usr/bin/env python3
"""File size checking script for benchmark_llm project.

Phase 1: Warnings only (exit code 0 always)
Phase 2: Enforce strict limits (exit code 1 on violations)

Usage:
    python scripts/check_file_size.py [directory]
    
Examples:
    python scripts/check_file_size.py src_v2
    python scripts/check_file_size.py tests
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Phase 1 limits (warnings only)
MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50
MAX_CLASS_LINES = 200

# File extensions to check
PYTHON_EXTENSIONS = {'.py'}

# Directories to skip
SKIP_DIRECTORIES = {
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'node_modules',
    '.pytest_cache',
    'Arquivos_Mortos',
    'data',
    'logs',
}


def count_lines(filepath: Path) -> int:
    """Count non-empty, non-comment lines in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    count = 0
    for line in lines:
        stripped = line.strip()
        # Skip empty lines and comments
        if stripped and not stripped.startswith('#'):
            count += 1
    
    return count


def check_file(filepath: Path) -> List[str]:
    """
    Check a single Python file for size violations.
    
    Args:
        filepath: Path to Python file
        
    Returns:
        List of warning messages (empty if no violations)
    """
    warnings = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Check file size
        if total_lines > MAX_FILE_LINES:
            warnings.append(
                f"⚠️  {filepath}: {total_lines} lines (limit: {MAX_FILE_LINES})"
            )
        
        # Parse AST for function and class sizes
        try:
            tree = ast.parse(''.join(lines))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Calculate function lines
                    if hasattr(node, 'end_lineno'):
                        func_lines = node.end_lineno - node.lineno + 1
                    else:
                        # Fallback for older Python versions
                        func_lines = _estimate_function_lines(node, lines)
                    
                    if func_lines > MAX_FUNCTION_LINES:
                        warnings.append(
                            f"⚠️  {filepath}:{node.lineno} function {node.name}() "
                            f"has {func_lines} lines (limit: {MAX_FUNCTION_LINES})"
                        )
                
                elif isinstance(node, ast.ClassDef):
                    # Calculate class lines
                    if hasattr(node, 'end_lineno'):
                        class_lines = node.end_lineno - node.lineno + 1
                    else:
                        # Fallback for older Python versions
                        class_lines = _estimate_class_lines(node, lines)
                    
                    if class_lines > MAX_CLASS_LINES:
                        warnings.append(
                            f"⚠️  {filepath}:{node.lineno} class {node.name} "
                            f"has {class_lines} lines (limit: {MAX_CLASS_LINES})"
                        )
        
        except SyntaxError:
            # Skip files with syntax errors (might be incomplete)
            pass
    
    except Exception as e:
        warnings.append(f"⚠️  {filepath}: Error reading file: {e}")
    
    return warnings


def _estimate_function_lines(node: ast.FunctionDef, lines: List[str]) -> int:
    """Estimate function lines for older Python versions."""
    # Count from function start to next statement at same indentation
    start_line = node.lineno - 1
    if start_line >= len(lines):
        return 1
    
    func_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    func_lines = 1
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip():  # Non-empty line
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= func_indent and not line.strip().startswith('#'):
                break
            func_lines += 1
    
    return func_lines


def _estimate_class_lines(node: ast.ClassDef, lines: List[str]) -> int:
    """Estimate class lines for older Python versions."""
    # Count from class start to next statement at same indentation
    start_line = node.lineno - 1
    if start_line >= len(lines):
        return 1
    
    class_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    class_lines = 1
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip():  # Non-empty line
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= class_indent and not line.strip().startswith('#'):
                break
            class_lines += 1
    
    return class_lines


def find_python_files(directory: Path) -> List[Path]:
    """
    Find all Python files in a directory recursively.
    
    Args:
        directory: Root directory to search
        
    Returns:
        List of Python file paths
    """
    python_files = []
    
    for path in directory.rglob('*.py'):
        # Skip directories in skip list
        if any(skip in path.parts for skip in SKIP_DIRECTORIES):
            continue
        
        # Skip __init__.py files (usually small)
        if path.name == '__init__.py':
            continue
        
        python_files.append(path)
    
    return python_files


def check_directory(directory: Path) -> Tuple[List[str], int]:
    """
    Check all Python files in a directory.
    
    Args:
        directory: Root directory to check
        
    Returns:
        Tuple of (list of all warnings, total files checked)
    """
    all_warnings = []
    files_checked = 0
    
    python_files = find_python_files(directory)
    
    for filepath in python_files:
        warnings = check_file(filepath)
        all_warnings.extend(warnings)
        files_checked += 1
    
    return all_warnings, files_checked


def main():
    """Main entry point."""
    # Determine directory to check
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        # Default to src_v2 if it exists, otherwise src
        directory = Path('src_v2')
        if not directory.exists():
            directory = Path('src')
    
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)
    
    print(f"🔍 Checking Python files in {directory}")
    print(f"Limits: files ≤{MAX_FILE_LINES} lines, "
          f"functions ≤{MAX_FUNCTION_LINES} lines, "
          f"classes ≤{MAX_CLASS_LINES} lines")
    print()
    
    # Check all files
    warnings, files_checked = check_directory(directory)
    
    # Output results
    if warnings:
        print(f"📊 Checked {files_checked} files")
        print()
        print(f"⚠️  Found {len(warnings)} warning(s):")
        print()
        for warning in warnings:
            print(warning)
        print()
    else:
        print(f"✅ All {files_checked} files within limits")
        print()
    
    # Phase 1: Always exit 0 (warnings only)
    print("Phase 1: Warnings only (no failures)")
    sys.exit(0)


if __name__ == '__main__':
    main()
