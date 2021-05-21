from typing import List, Optional, Tuple

MODE: str = 'DATABASE'  # DATABASE, AGENT

# ONLY IF MODE = DATABASE

DATABASE_ADDRESS: Optional[Tuple[str, int, str]] = ('127.0.0.1', 5432, 'test')
# DATABASE_ADDRESS: Optional[Tuple[str, int, str]] = None
DATABASE_CRED: Optional[Tuple[str, str]] = ('monitor', '12345')
# DATABASE_CRED: Optional[Tuple[str, str]] = None

# ONLY IF MODE = AGENT

# AGENT_ADDRESSES: List[str] = [
# 'http://127.0.0.1:8080',
# ]
AGENT_ADDRESSES: List[str] = []
