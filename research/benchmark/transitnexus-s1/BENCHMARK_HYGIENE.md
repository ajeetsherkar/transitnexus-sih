# Benchmark Hygiene — Before Every Benchmark Run

Purpose: Keep benchmark conditions consistent, fair and reproducible.

## Pre-run checklist

- [ ] Laptop is plugged into power.
- [ ] Power mode is set to high performance.
- [ ] Battery saver / low-power mode is OFF.
- [ ] Unnecessary background applications are closed.
- [ ] Laptop is cool and has adequate ventilation.
- [ ] Use the same terminal and Python environment.
- [ ] Screen recording is OFF.
- [ ] Network is OFF if the benchmark does not require it.

## Before starting measurements

- [ ] Confirm the correct model and runtime.
- [ ] Confirm input size, batch size and precision.
- [ ] Use the same input data and preprocessing.
- [ ] Run warm-up iterations before timed iterations.
- [ ] Record the environment and benchmark configuration.
- [ ] Keep per-iteration latency measurements.

## During and after the run

- [ ] Watch for latency drifting upward during the run.
- [ ] Avoid other CPU-intensive work.
- [ ] Do not silently delete unusual measurements.
- [ ] Report mean, median, P95, P99 and standard deviation.
- [ ] Save results and metadata with the benchmark output.

## Benchmark principle

Change one variable at a time. Keep all other conditions
consistent when comparing PyTorch CPU and ONNX Runtime CPU.

## Timing and garbage collection

- Use time.perf_counter() to measure elapsed inference time.
- Avoid time.time() for precise latency measurements because it measures wall-clock time.
- Python garbage collection (GC) automatically reclaims unreachable cyclic objects.
- Call gc.collect() once before warm-up, outside the timed loop, for a consistent cleanup point.
- Never call gc.collect() inside every timed iteration.
- Apply the same GC policy to both runtimes.

Decision: Use time.perf_counter(). Perform one explicit GC pass
before warm-up, outside the timed region.

## First-call overhead experiment

Experiment: Dummy workload with simulated lazy initialization.

| Measurement | Observed time |
|---|---:|
| Iteration 1 | 12.1793 ms |
| Iteration 50 | 0.0548 ms |
| Average, iterations 2-50 | 0.0525 ms |

Finding:
- First call was approximately 222 times slower than iteration 50.
- The first call created a lookup table of 500,000 values.
- Later calls reused the initialized lookup table.
- This demonstrates why first-call overhead should not be mixed
  with steady-state inference latency.

Benchmark decision:
- Perform warm-up iterations before collecting measurements.
- Keep initialization and compilation outside the timed region
  when measuring steady-state inference.
- Report initialization time separately if it matters to deployment.

## Thermal throttling and CPU frequency scaling

Hardware tested:
- Device: MacBook Air
- Chip: Apple M2
- Model identifier: Mac14,2
- Low Power Mode: OFF during inspection
- macOS thermal warning: None recorded during inspection

Key concepts:
- Thermal throttling occurs when the processor reduces performance
  to manage temperature.
- CPU frequency scaling dynamically adjusts processor speed.
- Latency drift may indicate thermal changes or background system load.

Benchmark hygiene:
- Keep the MacBook on a hard, flat surface.
- Keep ventilation unobstructed.
- Close unnecessary CPU-intensive applications.
- Allow cool-down periods between repeated long benchmark runs.
- Inspect per-iteration latency for possible performance drift.
- Do not claim thermal throttling without supporting evidence.

Note: The inspection showed no recorded thermal or performance
warning. This is not proof that throttling cannot occur.
