import gc
import time

lookup_table = None


def dummy_workload():
    global lookup_table

    # Simulate lazy initialization
    if lookup_table is None:
        lookup_table = [i * i for i in range(500_000)]

    # Simulate repeated computation
    return sum(lookup_table[:10_000])


def measure():
    gc.collect()  # Outside the timed region

    timings = []

    for iteration in range(1, 51):
        start = time.perf_counter()
        dummy_workload()
        elapsed = time.perf_counter() - start

        timings.append(elapsed * 1000)

    print("\n========== FIRST-CALL OVERHEAD ==========")
    print(f"Iteration 1:  {timings[0]:.4f} ms")
    print(f"Iteration 50: {timings[49]:.4f} ms")
    print(f"Average (2-50): {sum(timings[1:]) / 49:.4f} ms")
    print("=========================================")


if __name__ == "__main__":
    measure()
