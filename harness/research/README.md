# research/: training tooling for the A / B / C experiment

Research tooling only. It does not change what Teeter measures, and nothing here is experiment data.

- `env.py`: a training environment for `models/quadruped.xml`, using the harness's own model loader, observation layout, push model and fall rule.
- `ppo.py`: a small PPO trainer with parallel CPU rollouts that exports an ONNX brain Teeter can load. The ONNX graph holds the stance and action scale.

```
python research/ppo.py --out brainA.onnx --push-max 0 --steps 400000 --seed 0
```

- `sampling.py`: the conditions a brain trains under: none (A), uniform over the declared box (B), half around Teeter's failures and half uniform (C). Sensor lag and friction are held out of training.
- `failures.py`: Teeter finds failures on a brain and writes them as training starts for C.
- `evaluate.py`: Teeter's measurements of one brain: uniform failure rate with a 95% Wilson interval, and the smallest failing requested push from the directed search.

Test box: set with `TEETER_PUSH_MAX` and `TEETER_BOX` (JSON overrides of single ranges). Choose it, and write it into the signed plan, before the real runs.

Pilots (2026-11-24, software checks, not experiment data; 200,000 to 300,000 training steps per brain, 300 test samples, one test seed):

- Declared box, pushes to 9 N.s: A, B and C indistinguishable (failure rates 2 to 4%, overlapping intervals, smallest failing requested push about 8.2 N.s for all). Pushes above about 8 N.s tip the stand-in whatever the brain does.
- Pushes to 6.5 N.s, original other ranges: A failed 0 of 300. Nothing to learn from.
- Pushes to 6.5 N.s, torque loss to 60%, slope to 25 deg, payload to 4 kg: A failed 21 to 24%. Here B and C differed from A (B: 0.3% and 13%; C: 0% and 0%, seeds 0 and 1). Two seeds are too few to rank B and C: B's two seeds differ by 13 points. C reaching 0% means the box is too easy for it, so a harder test box is needed to separate B from C. The test box was chosen after seeing A fail, so it must be fixed in the plan before the real runs.

Pilot 3 (2026-11-24, software check, not experiment data; five seeds per brain, 200,000 steps for A and 300,000 more for B and C, 300 uniform test samples each, test seed 100). Box: pushes to 6.5 N.s, torque loss to 80%, slope to 30 deg, payload to 5 kg, the other ranges as declared.

| Brain | Failures of 300 per seed | Mean |
| --- | --- | --- |
| A | 76, 80, 80, 78, 70 | 76.8 (about 26%) |
| B | 36, 59, 70, 61, 38 | 52.8 (about 18%) |
| C | 10, 13, 22, 15, 14 | 14.8 (about 5%) |

C failed less than B in all five seeds. With sensor lag added as a condition nobody trained on, the same order held (A 62.6, B 40.6, C 7.2). Caveats: C's training starts were found by Teeter's search in the same box it is tested in, so some of C's edge may be familiarity with that box. Friction is not yet tested, the box was chosen after seeing A fail, and one test seed was used. These are pilot numbers for planning, not a result.

Held-out tests on the pilot-3 brains (2026-11-24, same caveats, fresh test seeds, 300 uniform samples per brain per test; mean failures of 300 over five seeds):

| Test | A | B | C |
| --- | --- | --- | --- |
| Friction added as a condition, friction_mu 0.3 to 0.9 (a proposed range), trained on none | 61.4 | 44.4 | 17.0 |
| Every trained range pushed 25% further out (torque loss capped at 95%), a region C's training starts never covered | 101.6 | 79.4 | 50.2 |

C failed less than B in all five seeds in both tests. The edge over B is smaller beyond the trained ranges (about 37% fewer failures) than inside them, which is the expected direction. Still a pilot: one simplified simulated robot, ranges chosen after the fact, one set of test seeds.
