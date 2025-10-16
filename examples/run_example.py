import sys
from pathlib import Path

# ensure project root (parent of this script's parent) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memstore import MemoryManager


def main():
    mgr = MemoryManager(storage_dir=str(ROOT / "memstore" / "data"))

    chat_log = """
Alice: Hey, did you see the new report on quarterly earnings?
Bob: Yes, I reviewed the document and left some notes.
System: ERROR Exception: NullReferenceException at line 42
Alice: Remind me to follow up with finance tomorrow.
User: This is a casual chat about vacation plans.
"""

    counts = mgr.ingest_chat_log(chat_log)
    print("Ingest counts:", counts)

    print('\nQuery conversations for "reviewed":')
    res = mgr.query("conversations", "reviewed")
    print(res)

    print('\nFind relevant for query "error":')
    rel = mgr.find_relevant("error")
    print(rel)


if __name__ == "__main__":
    main()
