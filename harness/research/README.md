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

Status (2026-11-24): the whole loop runs: train A, find failures, fine-tune B and C from A, evaluate. A pilot (200,000 training steps each, 200 test samples each, not experiment data) found A, B and C indistinguishable: failure rates 2 to 4% with overlapping intervals, smallest failing requested push about 8.2 N.s for all three. Pushes above about 8 N.s tip this stand-in whatever the brain does, so the declared box as it stands cannot separate the brains. The test box has to be chosen so failures depend on the brain, before the signed experiment starts.
