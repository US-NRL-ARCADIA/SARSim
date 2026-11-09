Here’s a concrete implementation plan tailored to a “team programming” setup where you provide guidance and a generative model writes most of the code.

I’ll keep this structured so you can hand individual tasks directly to the model, while you stay at the architectural/review level.

 


## **0. Working Mode & Conventions**

**Goal:** Make the repo “AI-friendly” and easy for you to oversee.

**Actions:**

1\. **Initialize the repository**

• Create sar-env/ with the exact directory structure specified in your design doc.

• Set up pyproject.toml with:

• Python 3.11+

• numpy, grpcio, grpcio-tools, protobuf, pytest, mypy, ruff, websockets or aiohttp (for WebSocket server), dataclasses (if needed for older Python) \[1].

• Set up pyproject.toml with:

• Add README.md with:

• Project description

• How to run tests

• How to run the server (once implemented)

• Add README.md with:

• Add run\_server.py stub that will later start gRPC + WebSocket engines.

2\. **CI/CD & quality gates**

• Under .github/workflows/test-and-lint.yml:

• Run pytest

• Run ruff (lint)

• Run mypy (type checking)

• Under .github/workflows/test-and-lint.yml:

• This ensures the generative model can’t silently break things.

3\. **Coding standards for the model**

• Enforce:

• Type hints everywhere

• Dataclasses for simple stateful objects (Agent, Casualty, BuildingCell)

• Separation: no imports from src/api or editor inside src/core (Model purity).

• Enforce:

• You can define a short “Contributor Guide” for the AI model:

• How to name files/classes

• How to write tests (pytest style)

• How to use enums vs. string literals for states.

• You can define a short “Contributor Guide” for the AI model:

 


## **1. Phase 1 – Core Physics & 3D Spatial Grid (Model Setup)**

**Objective:** Implement the foundational spatial grid and agent movement, with tests.


### **1.1 Files & components**

• src/core/grid.py

• src/core/entities.py (agent skeleton only at this phase)

• tests/test\_physics.py


### **1.2 Implementation tasks**

1\. **Spatial grid core**

• Implement Coordinate dataclass (as in the blueprint).

• Implement SpatialGrid class:

• Properties:

• N, Z

• status\_grid: NumPy int32 array $$ (N, N, Z) $$ coded as:

• 0 = UNOCCUPIED

• 1 = PASSABLE

• 2 = IMPASSABLE

• status\_grid: NumPy int32 array $$ (N, N, Z) $$ coded as:

• smoke\_grid: NumPy float32 array $$ (N, N, Z) $$ with $$ D \in \[0.0, 1.0] $$.

• entity\_locations: Dict\[Tuple\[int,int,int], list].

• Properties:

• Methods:

• is\_in\_bounds(coord: Coordinate) -> bool

• evaluate\_cell\_status(coord: Coordinate, agent\_class: str) -> int (from blueprint, with UAV special-case).

• set\_cell\_status(coord, status)

• add\_entity(coord, entity)

• remove\_entity(coord, entity)

• Helper: get\_entities(coord) -> list

• Methods:

• Implement SpatialGrid class:

2\. **Agent representation**

• In src/core/entities.py:

• Define Orientation enum (NORTH, EAST, SOUTH, WEST).

• Define AgentClass enum (UGV, UAV).

• Define Agent dataclass:

• id: str

• coord: Coordinate

• orientation: Orientation

• agent\_class: AgentClass

• busy\_ticks\_remaining: int = 0

• last\_error: Optional\[str] = None

• Define Agent dataclass:

• Keep only movement logic here (no networking/telemetry yet).

• In src/core/entities.py:

3\. **Movement functions**

• In grid.py or entities.py (your choice, but keep in Model):

• move\_forward(agent: Agent) -> Tuple\[bool, str]:

• Compute new coordinate based on orientation and current z.

• Check:

• is\_in\_bounds

• evaluate\_cell\_status rules:

• UGV cannot enter PASSABLE or IMPASSABLE at $$ z = 0 $$.

• UAV may ignore ground-level obstacles at $$ z = 0 $$ but must respect elements at its own $$ z $$.

• evaluate\_cell\_status rules:

• Co-occupancy constraints:

• No agent can occupy same $$ (x, y, z) $$ as another agent.

• Co-occupancy constraints:

• Check:

• If blocked, return False, "OUT\_OF\_BOUNDS" or "IMPASSABLE" or "COLLISION\_OCCURRED" and do not update agent position.

• move\_forward(agent: Agent) -> Tuple\[bool, str]:

• turn\_left(agent) and turn\_right(agent) (orientation rotation).

• ascend(agent) / descend(agent) for UAV, bounded by $$ 1 \le z \le Z-1 $$.

• In grid.py or entities.py (your choice, but keep in Model):

4\. **Collision/constraint enforcement**

• Implement checks consistent with section 6.1–6.3:

• UAV/UGV horizontal co-location allowed if $$ z $$ differs.

• No two agents on same $$ (x,y,z) $$.

• Agents locked to: UGV $$ z=0 $$, UAV $$ z \ge 1 $$.

• Implement checks consistent with section 6.1–6.3:


### **1.3 Tests**

• In tests/test\_physics.py:

• test\_agent\_forward\_movement\_out\_of\_bounds() (from the design doc).

• Add:

• test\_ugv\_blocked\_by\_passable\_debris()

• test\_uav\_can\_fly\_over\_ground\_debris()

• test\_no\_two\_agents\_same\_cell()

• Add:

• Run under CI.

**Milestone:** All movement tests pass; grid behaves deterministically.

 


## **2. Phase 2 – Entity System & Structural Modeling (Model Extension)**

**Objective:** Add casualties, buildings, debris stacking, and interaction actions to Model.


### **2.1 Files & components**

• src/core/entities.py (extended)

• Possibly src/core/grid.py enhancements

• tests/test\_entities.py


### **2.2 Implementation tasks**

1\. **Casualty model**

• Extend entities.py with:

• TriageState enum

• LivingState enum (ALIVE, DECEASED)

• Casualty dataclass:

• id: str

• coord: Coordinate

• health: float $$ \in \[0.0, 100.0] $$

• decay\_rate: float

• is\_covered: bool

• triage\_state: TriageState

• transport\_status: str (e.g., ON\_GROUND, LOADED, UNLOADED)

• living\_state: LivingState

• Casualty dataclass:

• Method update\_health(smoke\_density: float) implementing:

• $$ H(t+1) = H(t) - Decay\_Rate $$

• Double decay\_rate if is\_covered or $$ D \ge 0.5 $$.

• Death transition if $$ H(t) \le 0 $$.

• Method update\_health(smoke\_density: float) implementing:

• Extend entities.py with:

2\. **Building & debris model**

• Define:

• BuildingCell dataclass:

• coord: Coordinate

• integrity: float $$ I\_c \in \[0.0,1.0] $$

• collapsed: bool

• BuildingCell dataclass:

• Building dataclass:

• id: str

• cells: Dict\[Tuple\[int,int,int], BuildingCell]

• Building dataclass:

• Define:

• Logic:

• Collapse rule when $$ I\_c < 0.2 $$:

• Mark cell collapsed=True.

• Set grid status\_grid to PASSABLE (debris at $$ z=0 $$).

• Apply casualty penalty:

• health -= 50.

• Apply casualty penalty:

• Agent handling:

• Agent in that cell: auto-move to adjacent free cell, mark “DAMAGED” (status tracked on Agent).

• Agent handling:

• Collapse rule when $$ I\_c < 0.2 $$:

• Logic:

3\. **Cover mechanic & actions**

• Implement vertical stacking:

• When debris (PASSABLE) present at casualty’s coordinate:

• Set casualty.is\_covered = True.

• When debris (PASSABLE) present at casualty’s coordinate:

• Implement vertical stacking:

• Implement “action hooks” (internal model APIs invoked by Controller later):

• breach\_entryway(agent, building\_cell):

• Multi-tick (5 ticks) action: to be driven by Controller, but Model defines effect: reduce some “blockade” metric.

• breach\_entryway(agent, building\_cell):

• clear\_debris(agent, coord):

• 3 ticks: change debris from PASSABLE to UNOCCUPIED, set casualty.is\_covered=False.

• clear\_debris(agent, coord):

• triage(agent, casualty):

• Requires adjacency, is\_covered=False, casualty ALIVE.

• After 10 ticks: set decay\_rate to stable Delta\_Stable.

• triage(agent, casualty):

• retrieve\_body(agent, casualty):

• Requires casualty DECEASED, is\_covered=False, adjacency. Set agent.payload = casualty with capacity 1.

• retrieve\_body(agent, casualty):

• Implement “action hooks” (internal model APIs invoked by Controller later):

4\. **Adjacency & constraints**

• Helper: are\_adjacent(coord\_a, coord\_b) -> bool (4-neighborhood or 8-neighborhood per your preference, but be consistent).

• Enforce:

• Agent must be adjacent (not co-located) for triage/load/retrieve.

• No triage/load when is\_covered=True.

• Enforce:


### **2.3 Tests**

• tests/test\_entities.py:

• test\_casualty\_health\_decay\_and\_death\_transition()

• test\_casualty\_cover\_blocks\_triage()

• test\_clear\_debris\_enables\_triage()

• test\_building\_collapse\_causes\_health\_penalty()

• test\_agent\_payload\_capacity\_one\_entity()

**Milestone:** Script scenario: agent breaches, clears debris, triages covered casualty inside building cell.

 


## **3. Phase 3 – Observability, Sensors, Obscurants, Events**

**Objective:** Implement sensor models, smoke/fog obscurants, local map accumulation, event system.


### **3.1 Files & components**

• src/core/grid.py (sensor methods)

• src/core/events.py

• Possibly src/core/entities.py (agent “mental map” or separate client-side model)

• Tests in tests/test\_physics.py and new tests/test\_events.py (optional)


### **3.2 Implementation tasks**

1\. **Raycasting & LOS**

• In grid.py, implement:

• raycast\_radial(origin: Coordinate, radius: int, agent\_class: AgentClass) -> List\[Coordinate]

• raycast\_cone(origin, orientation, angle, max\_distance) -> List\[Coordinate]

• In grid.py, implement:

• LOS rules:

• Stop ray when encountering IMPASSABLE.

• Smoke/fog:

• If smoke\_grid\[x,y,z] >= 0.5, mark cell as UNKNOWN in observation results.

• Smoke/fog:

• LOS rules:

2\. **Obscurant & noise**

• Add:

• apply\_gaussian\_noise(observation):

• Simulate degraded sensor readings; for example, random mislabel with probability dependent on D.

• apply\_gaussian\_noise(observation):

• Add:

• Observations could be represented as a data structure:

• Observation containing list of visible cells with states, plus unknowns.

• Observations could be represented as a data structure:

3\. **Local map accumulation**

• You may define a separate client-side Python model (used by test agents but not necessarily in main repo yet), e.g.:

• LocalMap class:

• Maintains known cells, updated by Observation objects.

• Emulates “agent’s mental map” stitching environment over time.

• LocalMap class:

• You may define a separate client-side Python model (used by test agents but not necessarily in main repo yet), e.g.:

4\. **Event system**

• src/core/events.py:

• Event dataclass (type, timestamp, payload).

• EventScheduler:

• Maintains:

• Stochastic events (random collapses based on building integrity).

• Scheduled events (medical reports to agents at ticks).

• Maintains:

• API:

• step\_events(current\_tick, grid, entities) -> List\[Event].

• API:

• EventScheduler:

• src/core/events.py:


### **3.3 Tests**

• Raycasting tests:

• test\_los\_blocked\_by\_impassable\_walls()

• test\_smoke\_masks\_cells\_as\_unknown()

• Event tests:

• Deterministic scheduled events using fixed seeds.

**Milestone:** Raycasting simulation and step-by-step “mental map” example working.

 


## **4. Phase 4 – API, Networking, Synchronization (Controller)**

**Objective:** Build gRPC and WebSocket controllers, time sync engine, concurrency resolution.


### **4.1 Files & components**

• proto/sar\_env.proto

• src/api/generated/ (compiled Python gRPC code)

• src/api/engine.py

• src/api/grpc\_server.py

• src/api/websocket\_server.py

• tests/test\_api.py

• tests/test\_concurrency.py


### **4.2 Implementation tasks**

1\. **Protobuf definitions**

• Design sar\_env.proto with:

• Messages:

• Coordinate, AgentState, CasualtyState, BuildingState

• ActionRequest, ActionResponse

• TelemetryLogEntry (for Phase 6)

• Messages:

• Services:

• EnvironmentService:

• rpc Step(ActionRequest) returns (StepResponse);

• rpc ConnectStream(stream ActionRequest) returns (stream StepResponse);

• EnvironmentService:

• AuditService (Phase 6).

• Services:

• Design sar\_env.proto with:

• Run python -m grpc\_tools.protoc to generate Python bindings in src/api/generated/.

2\. **Simulation engine (Controller core)**

• src/api/engine.py:

• SimulationEngine class:

• Holds:

• SpatialGrid, collections of Agent, Casualty, Building.

• EventScheduler.

• Holds:

• Execution loop:

• step(actions\_by\_agent\_id: Dict\[str, Action]) -> None:

1\. Resolve active actions (busy timers).

• 

1\. Apply physical transitions (health, integrity, smoke).

• 

1\. Evaluate hazards/events (via EventScheduler).

• 

1\. Emit telemetry logs (Phase 6).

• 

1\. Generate sensor observations per agent (raycasting).

• 

• step(actions\_by\_agent\_id: Dict\[str, Action]) -> None:

• Execution loop:

• Synchronous/async modes:

• Synchronous: respect $$ T\_{budget} = 100 ms $$; missing actions => STALL.

• Asynchronous: ticks at fixed interval (e.g., 100 ms) independent of client responses (using asyncio loop).

• Synchronous/async modes:

• SimulationEngine class:

• src/api/engine.py:

3\. **Action duration/busy state**

• Implement state machine:

• Actions with durations:

• breach, clear\_debris, triage, load, unload, retrieve.

• Actions with durations:

• For each agent:

• busy\_ticks\_remaining > 0 => no new actions; continue countdown each tick.

• When reaches 0, finalize multi-tick effect (e.g., debris cleared).

• For each agent:

• Implement state machine:

4\. **Concurrency conflict solver**

• In SimulationEngine:

• resolve\_concurrent\_actions(actions, strategy="PRIORITY\_BASED")

• Evaluate target coordinates for movement-type actions.

• If multiple agents target same empty cell:

• Sort by priority:

• Class priority (UAV > UGV)

• Then by Agent ID (alphabetical).

• Sort by priority:

• Winner moves; losers remain and set MOVEMENT\_BLOCKED (and optionally COLLISION\_OCCURRED if collided with agent already there).

• If multiple agents target same empty cell:

• resolve\_concurrent\_actions(actions, strategy="PRIORITY\_BASED")

• In SimulationEngine:

5\. **gRPC server**

• src/api/grpc\_server.py:

• Implement EnvironmentServiceServicer:

• Step: map ActionRequest to internal action object, call SimulationEngine.step, return StepResponse including updated state and diagnostics.

• ConnectStream: maintain bidirectional stream; for each tick, read actions from clients, call step, send responses.

• Implement EnvironmentServiceServicer:

• Use asyncio or standard gRPC, depending on your preference.

• src/api/grpc\_server.py:

6\. **WebSocket server (optional alternative)**

• src/api/websocket\_server.py:

• Implement JSON bridge to same SimulationEngine API.

• Use websockets or aiohttp to:

• Accept connections.

• Parse JSON actions.

• Send JSON telemetry / state.

• Use websockets or aiohttp to:

• src/api/websocket\_server.py:


### **4.3 Tests**

• tests/test\_api.py:

• Basic gRPC connection tests.

• Step call with simple move action -> validate coordinates.

• tests/test\_concurrency.py (as in doc):

• test\_simultaneous\_movement\_collision() using SimulationEngine.resolve\_concurrent\_actions.

**Milestone:** Two mock agents connect via gRPC, perform concurrent actions; conflict resolution matches design.

 


## **5. Phase 5 – Serialization, Procedural Generation, Editor (View)**

**Objective:** Build map serialization, procedural generator, and WYSIWYG editor.


### **5.1 Files & components**

• src/utils/serializer.py

• src/utils/generator.py

• editor/app.py

• editor/assets/ (icons, tiles)

• Tests: tests/test\_utils.py (for serializer/generator)


### **5.2 Implementation tasks**

1\. **Unified serializer**

• serializer.py:

• Design a unified schema (JSON/YAML) for:

• Grid size

• Buildings (cells, integrity)

• Casualties (coords, health, decay, covered flag)

• Initial smoke densities

• Drop-off zones / medical centers.

• Design a unified schema (JSON/YAML) for:

• Functions:

• serialize\_state(grid, agents, casualties, buildings, events) -> Dict

• deserialize\_state(config: Dict) -> (grid, agents, casualties, buildings, events)

• Functions:

• serializer.py:

• Support JSON and YAML:

• Use json and pyyaml (if allowed).

• Support JSON and YAML:

2\. **Procedural generator**

• generator.py:

• Inputs:

• grid\_size, z\_depth

• Density parameters: building density, hazard density, casualty density, debris density.

• RNG seed.

• Inputs:

• Outputs:

• In-memory state objects (grid + entities) or directly a config dict that can be serialized.

• Outputs:

• Typical algorithms:

• Place buildings randomly with sizes and integrities.

• Place casualties with random health/covered state.

• Generate smoke patches.

• Typical algorithms:

• generator.py:

3\. **Visual layout editor**

• editor/app.py:

• Choose Pygame or PyQt6; I suggest Pygame for simple grid painting.

• Features:

• Render grid as tiles.

• Add tools:

• Paint cell type (UNOCCUPIED/PASSABLE/IMPASSABLE).

• Place/modify casualties (click to open side panel with sliders for health, decay\_rate, is\_covered).

• Place buildings and set integrity.

• Add tools:

• Export button:

• Uses serializer.py to export to JSON/YAML.

• Export button:

• Load button:

• Load config and re-display.

• Load button:

• Features:

• editor/app.py:


### **5.3 Tests**

• tests/test\_utils.py:

• test\_round\_trip\_serialization():

• Generate map with generator.py.

• Serialize to JSON.

• Deserialize and assert equivalence.

• test\_round\_trip\_serialization():

• Manual test:

• Generate map programmatically, open in editor, adjust casualty health, re-export; check JSON content.

**Milestone:** Fully functional editor + generator + serializer loop.

 


## **6. Phase 6 – Telemetry, Auditing, External Verification**

**Objective:** Implement logging, telemetry streams, and audit gRPC service.


### **6.1 Files & components**

• Extend:

• src/api/engine.py (hooks)

• src/api/grpc\_server.py (audit service)

• Telemetry types defined in sar\_env.proto

• Tests: tests/test\_api.py or tests/test\_telemetry.py


### **6.2 Implementation tasks**

1\. **Telemetry pipeline**

• In SimulationEngine:

• Define event hooks:

• COLLISION\_EVENT

• CELL\_TRANSITION\_EVENT

• CASUALTY\_STATE\_CHANGE\_EVENT

• STRUCTURAL\_COLLAPSE\_EVENT

• Define event hooks:

• Each action in Model/Controller should call a logging function:

• log\_event(event\_type, payload).

• Each action in Model/Controller should call a logging function:

• In SimulationEngine:

2\. **Logging interface**

• Implement internal asynchronous queue:

• telemetry\_queue: asyncio.Queue\[TelemetryLogEntry]

• Implement internal asynchronous queue:

• On each step, push relevant entries to this queue.

3\. **Audit gRPC service**

• In sar\_env.proto:

• rpc SubscribeTelemetry(TelemetrySubscriptionRequest) returns (stream TelemetryLogEntry);

• In sar\_env.proto:

• In grpc\_server.py:

• Implement AuditServiceServicer.SubscribeTelemetry:

• For each connected audit client:

• Stream entries from telemetry\_queue in order.

• For each connected audit client:

• Implement AuditServiceServicer.SubscribeTelemetry:

• In grpc\_server.py:


### **6.3 Tests**

• Start SimulationEngine with a simple scenario.

• Run a mock audit client in test:

• Connect to SubscribeTelemetry.

• Drive simulation for several ticks.

• Assert the sequence of events matches expected order and contents.

**Milestone:** External client sees chronological ledger of collisions, triage, debris clearing etc.

 


## **7. How You Can Work With the Generative Model**

To make this practical for you:

1\. **Work in “small slices”**

• For each of the tasks above, you can give the model a specific file + function to implement plus constraints:

• “Implement SpatialGrid with these member variables and methods, using NumPy, no external imports beyond X, and write minimal unit tests in tests/test\_physics.py.”

• For each of the tasks above, you can give the model a specific file + function to implement plus constraints:

2\. **Use tests as guardrails**

• Start each feature by writing the tests (possibly by hand or via the model under your direction).

• Then ask the model to implement code that passes those tests.

• This keeps behavior aligned to the spec.

3\. **Aggressive timeline**

• Because the model is doing most coding, you can proceed phase-by-phase quickly:

• Phase 1–2 in a few working sessions.

• Phase 3–4 next.

• Phase 5–6 last.

• Because the model is doing most coding, you can proceed phase-by-phase quickly:

• CI will tell you when something breaks as you move fast.

4\. **Review strategy**

• You focus on:

• Architectural integrity (no violations of MVC).

• Performance/complexity.

• Correct enforcement of constraints (especially co-occupancy, decay rules, and multi-tick actions).

• You focus on:

• The model focuses on:

• Boilerplate

• Implementation details

• Tests and serialization.

• The model focuses on:

 

If you’d like, I can next:

• Draft the initial pyproject.toml, README.md, and .github/workflows/test-and-lint.yml.

• Or, design the sar\_env.proto message and service definitions in detail so the model can implement gRPC right away.
