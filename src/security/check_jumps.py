from spoofing_detection import run_spoofing_detection

violations, df = run_spoofing_detection()
jumps = [v for v in violations if v["type"] == "position_jump"]

for v in jumps:
    print(v)