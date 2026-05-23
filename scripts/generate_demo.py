"""Render one step of the GadsChain demo: types the call slowly, then prints the return."""
import sys
import time


STEPS = {
    "1": (
        'get_campaigns(customer_id="your-account")',
        "Increase Sales — $20/day — 4.81% CTR",
    ),
    "2": (
        'get_search_terms(campaign_id="23658813091", days=28)',
        "50 search terms — Friday CPC anomaly detected",
    ),
    "3": (
        'add_negative_keywords(keywords=["free pizza", "recipe"])',
        "2 negative keywords added — waste eliminated",
    ),
}


def slow_type(text: str, delay: float = 0.035) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "1"
    if step not in STEPS:
        print(f"unknown step: {step}", file=sys.stderr)
        sys.exit(1)
    call, ret = STEPS[step]
    slow_type(f"> {call}")
    time.sleep(0.5)
    print(f"[returns] {ret}")


if __name__ == "__main__":
    main()
