import time
import os

def main():
    phase = int(os.getenv('PHASE', 1))
    
    print("=" * 60)
    print("FDS Pipeline Consumer")
    print(f"Phase: {phase}")
    print("=" * 60)
    
    if phase == 1:
        print("[Phase 1] Consumer not needed - Generator inserts directly to DB")
        print("[Phase 1] Waiting for Phase 3...")
        while True:
            time.sleep(60)
    else:
        print(f"[Error] Phase {phase} not implemented yet")

if __name__ == "__main__":
    main()
