"""Command-line argument utilities."""
from typing import List


def has_flag(args: List[str], flag: str) -> bool:
    """Check if a flag is present in argv.
    
    Supports both formats:
    - Space-separated: --flag value
    - Equals: --flag=value
    
    Args:
        args: Command-line arguments (without script name)
        flag: Flag to search for (e.g., "--help")
        
    Returns:
        True if flag is present, False otherwise
    """
    for arg in args:
        # Exact match: --flag
        if arg == flag:
            return True
        
        # Equals notation: --flag=value
        if arg.startswith(f"{flag}="):
            return True
    
    return False
