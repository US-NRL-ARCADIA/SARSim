# Trained SARSim agents

This directory stores ready-to-run DQN checkpoints. Each agent consists of:

- `<name>.safetensors` — MLX network weights
- `<name>.json` — architecture, training, and evaluation metadata

Checkpoints can be selected in the **RL training** tab and run against a loaded
scenario with the same grid size. Training uses Apple MLX/Metal on Apple Silicon
and a utilitarian reward: living rescues dominate reward, casualty deaths carry
an equal negative penalty, body recovery has only small value, and time plus
aggregate health loss are penalized.

The planner-guided DQN receives map tensors plus shortest-path guidance and can
learn to accept or override that guidance based on long-term casualty utility.
Its compact policy actions are `MOVE_FORWARD`, `TURN_LEFT`, `TURN_RIGHT`,
`INTERACT`, and `WAIT`. `INTERACT` resolves against simulator state to clear a
covered casualty, load/retrieve an adjacent casualty, breach an obstacle, or
transfer a payload to a field hospital. Contextually impossible actions are
masked during deployment.
