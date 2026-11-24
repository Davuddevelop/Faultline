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
