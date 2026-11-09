import React, { useEffect, useRef, useState } from "react";
import "./App.css";
import { StateSnapshot, AgentState, CasualtyState, EventModel } from "./types";
import GridView from "./GridView"
import allFeaturesDemoScript from "./all_features_demo_script.json";

const API_BASE = "http://localhost:8000";

const SCENARIO_OPTIONS = [
  "editor/last_scenario.json",
  "editor/uav_scenario.json",
  "editor/breach_scenario.json",
  "editor/retrieve_scenario.json",
  "editor/smoke_health_scenario.json",
  "editor/smoke_obscure_scenario.json",
  "editor/multi_casualty_scenario.json",
  "editor/field_hospital_transport_scenario.json",
  "editor/action_script_all_features.json",
];
const DEV_SCENARIO_OPTION = "Dev Scenario";

type ScriptActionType =
  | "MOVE_FORWARD"
  | "TRIAGE"
  | "CLEAR_DEBRIS"
  | "RETRIEVE_BODY"
  | "LOAD_CASUALTY"
  | "UNLOAD_CASUALTY"
  | "TRANSFER_CASUALTY"
  | "BREACH_ENTRYWAY"
  | "ASCEND"
  | "DESCEND"
  | "TURN_LEFT"
  | "TURN_RIGHT";

interface ScriptAction {
  actor_id: string;
  action_type: ScriptActionType;
  target_casualty_id?: string;
  target_coord?: { x: number; y: number; z: number };
  duration?: number;
  label?: string;
}

interface ActionScript {
  environment?: string;
  delay_ms?: number;
  actions: ScriptAction[];
}

type KeyAction = Pick<ScriptAction, "action_type"> &
  Pick<ScriptAction, "target_casualty_id" | "target_coord">;

const DEMO_SCRIPT = allFeaturesDemoScript as unknown as ActionScript;

function App() {
  const [state, setState] = useState<StateSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<EventModel[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedCasualtyId, setSelectedCasualtyId] = useState<string | null>(null);
  const [selectedCasualtyStackIds, setSelectedCasualtyStackIds] = useState<string[]>([]);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [zLevel, setZLevel] = useState<number>(0);
  const [scenarioPath, setScenarioPath] = useState<string>(DEV_SCENARIO_OPTION);
  const [scenarioJson, setScenarioJson] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [scriptJson, setScriptJson] = useState(() => JSON.stringify(DEMO_SCRIPT, null, 2));
  const [isPlayingScript, setIsPlayingScript] = useState(false);
  const [scriptProgress, setScriptProgress] = useState("");
  const [keyboardHighlight, setKeyboardHighlight] = useState<ScriptActionType[]>([]);
  const [keyboardStatus, setKeyboardStatus] = useState("");
  const runIntervalRef = useRef<number | null>(null);
  const initialEnvironmentLoadRef = useRef<Promise<void> | null>(null);
  const keyboardActionInProgressRef = useRef(false);
  const keyboardHighlightTimerRef = useRef<number | null>(null);
  const agents: AgentState[] = state ? Object.values(state.agents) : [];
  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  useEffect(() => {
    if (!state) return;
    if (selectedAgentId && state.agents[selectedAgentId]) return;

    const defaultAgent = state.agents.A1 ?? Object.values(state.agents)[0];
    setSelectedAgentId(defaultAgent?.id ?? null);
  }, [state, selectedAgentId]);

  // Fetch current state
  const fetchState = async () => {
    try {
      setLoading(true);
      const resp = await fetch(`${API_BASE}/state`);
      if (!resp.ok) {
        throw new Error(`GET /state failed: ${resp.status}`);
      }
      const data: StateSnapshot = await resp.json();
      setState(data);
      if (data.ended) setIsRunning(false);
      setEvents(data.events ?? []);
      if (selectedZoneId && !(data.zones ?? []).some((z) => z.id === selectedZoneId)) {
        setSelectedZoneId(null);
      }
    } catch (err: any) {
      setError(err.message ?? String(err));
    } finally {
      setLoading(false);
    }
  };

  // Initialize dev scenario
  const initDev = async () => {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/init/dev`, {
        method: "POST",
      });
      if (!resp.ok) {
        throw new Error(`POST /init/dev failed: ${resp.status}`);
      }
      setScenarioPath(DEV_SCENARIO_OPTION);
      await fetchState();
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  const loadScenarioFromPath = async () => {
    try {
      setError(null);
      const isDevScenario = scenarioPath === DEV_SCENARIO_OPTION;
      const resp = await fetch(`${API_BASE}/${isDevScenario ? "init/dev" : "scenario/load-from-path"}`, {
        method: "POST",
        ...(isDevScenario ? {} : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filepath: scenarioPath }),
        }),
      });
      if (!resp.ok) {
        throw new Error(`POST scenario load failed: ${resp.status}`);
      }
      await fetchState();
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  const loadScenarioFromJson = async () => {
    try {
      setError(null);
      const parsed = JSON.parse(scenarioJson);
      const resp = await fetch(`${API_BASE}/scenario/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: parsed }),
      });
      if (!resp.ok) {
        throw new Error(`POST /scenario/load failed: ${resp.status}`);
      }
      await fetchState();
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  const resetScenario = async () => {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/reset`, {
        method: "POST",
      });
      if (!resp.ok) {
        throw new Error(`POST /reset failed: ${resp.status}`);
      }
      // Clear local UI state too
      setState(null);
      setEvents([]);
      setSelectedAgentId(null);
      setSelectedCasualtyId(null);
      setSelectedCasualtyStackIds([]);
      setSelectedZoneId(null);
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  // Step one tick
  const stepOneTick = async () => {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticks: 1 }),
      });
      if (!resp.ok) {
        throw new Error(`POST /step failed: ${resp.status}`);
      }
      const data: StateSnapshot = await resp.json();
      setState(data);
      setEvents(data.events ?? []);
      if (selectedZoneId && !(data.zones ?? []).some((z) => z.id === selectedZoneId)) {
        setSelectedZoneId(null);
      }
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  const sendAction = async (payload: object) => {
    try {
      setError(null);
      const resp = await fetch(`${API_BASE}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const bodyText = await resp.text();
        throw new Error(`POST /actions failed: ${resp.status}${bodyText ? ` - ${bodyText}` : ""}`);
      }
      await fetchState();
    } catch (err: any) {
      setError(err.message ?? String(err));
    }
  };

  const doMoveForward = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `move_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "MOVE_FORWARD",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doTurnLeft = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `turnL_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "TURN_LEFT",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doTurnRight = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `turnR_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "TURN_RIGHT",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doAscend = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `ascend_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "ASCEND",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doDescend = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `descend_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "DESCEND",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doClearDebris = async () => {
    if (!selectedAgentId || !selectedCasualty) {
      setError("Select an agent and a casualty first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `clear_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "CLEAR_DEBRIS",
          target_coord: {
            x: selectedCasualty.x,
            y: selectedCasualty.y,
            z: selectedCasualty.z,
          },
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doBreach = async () => {
    if (!selectedAgentId || !selectedBuildingCell) {
      setError("Select an agent and a building first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `breach_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "BREACH_ENTRYWAY",
          target_coord: {
            x: selectedBuildingCell.x,
            y: selectedBuildingCell.y,
            z: selectedBuildingCell.z,
          },
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doRetrieveBody = async () => {
    if (!selectedAgentId || !selectedCasualtyId) {
      setError("Select an agent and a casualty first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `retrieve_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "RETRIEVE_BODY",
          target_casualty_id: selectedCasualtyId,
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doLoadCasualty = async () => {
    if (!selectedAgentId || !selectedCasualtyId) {
      setError("Select an agent and a casualty first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `load_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "LOAD_CASUALTY",
          target_casualty_id: selectedCasualtyId,
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doUnloadCasualty = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `unload_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "UNLOAD_CASUALTY",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doTransferCasualty = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    await sendAction({
      actions: [
        {
          action_id: `transfer_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "TRANSFER_CASUALTY",
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const doTriage = async () => {
    if (!selectedAgentId) {
      setError("Select an agent first.");
      return;
    }
    if (!state) {
      setError("No state loaded.");
      return;
    }

    let targetId: string | null = selectedCasualtyId;

    if (!targetId) {
    const casualtiesList = Object.values(state.casualties);
    if (casualtiesList.length === 0) {
      setError("No casualties to triage.");
      return;
    }
      targetId = casualtiesList[0].id;
    }

    await sendAction({
      actions: [
        {
          action_id: `triage_${Date.now()}`,
          actor_id: selectedAgentId,
          action_type: "TRIAGE",
          target_casualty_id: targetId,
          start_tick: 0,
          duration: 0,
        },
      ],
    });
    await stepOneTick();
  };

  const flashKeyboardActions = (actionTypes: ScriptActionType[]) => {
    setKeyboardHighlight(actionTypes);
    if (keyboardHighlightTimerRef.current !== null) {
      window.clearTimeout(keyboardHighlightTimerRef.current);
    }
    keyboardHighlightTimerRef.current = window.setTimeout(() => {
      setKeyboardHighlight([]);
      keyboardHighlightTimerRef.current = null;
    }, 650);
  };

  const executeKeyboardActions = async (
    actions: KeyAction[],
    highlightedActions: ScriptActionType[],
    status: string,
  ) => {
    if (!selectedAgentId) {
      setKeyboardStatus("Select an agent before using the keyboard controls.");
      setError("Select an agent first.");
      return;
    }
    if (keyboardActionInProgressRef.current) return;

    keyboardActionInProgressRef.current = true;
    setError(null);
    setKeyboardStatus(status);
    flashKeyboardActions(highlightedActions);
    try {
      const actionResponse = await fetch(`${API_BASE}/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actions: actions.map((action, index) => ({
            action_id: `keyboard_${Date.now()}_${index}`,
            actor_id: selectedAgentId,
            action_type: action.action_type,
            target_casualty_id: action.target_casualty_id,
            target_coord: action.target_coord,
            start_tick: 0,
            duration: 0,
          })),
        }),
      });
      if (!actionResponse.ok) {
        const details = await actionResponse.text();
        throw new Error(`Action failed to queue: ${details || actionResponse.status}`);
      }

      const stepResponse = await fetch(`${API_BASE}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticks: 1 }),
      });
      if (!stepResponse.ok) throw new Error(`Action failed to step: ${stepResponse.status}`);
      const nextState: StateSnapshot = await stepResponse.json();
      setState(nextState);
      setEvents(nextState.events ?? []);
      const activeAgent = nextState.agents[selectedAgentId];
      if (activeAgent) setZLevel(activeAgent.z);
    } catch (err: any) {
      setError(err.message ?? String(err));
    } finally {
      keyboardActionInProgressRef.current = false;
    }
  };

  const moveSelectedAgentInDirection = async (direction: "NORTH" | "EAST" | "SOUTH" | "WEST", key: string) => {
    if (!selectedAgent) {
      setKeyboardStatus(`${key.toUpperCase()} · select an agent to move`);
      setError("Select an agent first.");
      return;
    }

    const directions = ["NORTH", "EAST", "SOUTH", "WEST"];
    const currentDirection = directions.indexOf(selectedAgent.orientation);
    const targetDirection = directions.indexOf(direction);
    if (currentDirection < 0) {
      setError(`Unknown agent orientation: ${selectedAgent.orientation}`);
      return;
    }

    const clockwiseTurns = (targetDirection - currentDirection + directions.length) % directions.length;
    const actions: KeyAction[] = [];
    const highlightedActions: ScriptActionType[] = ["MOVE_FORWARD"];
    if (clockwiseTurns === 1) {
      actions.push({ action_type: "TURN_RIGHT" });
      highlightedActions.unshift("TURN_RIGHT");
    } else if (clockwiseTurns === 2) {
      actions.push({ action_type: "TURN_RIGHT" }, { action_type: "TURN_RIGHT" });
      highlightedActions.unshift("TURN_RIGHT");
    } else if (clockwiseTurns === 3) {
      actions.push({ action_type: "TURN_LEFT" });
      highlightedActions.unshift("TURN_LEFT");
    }
    actions.push({ action_type: "MOVE_FORWARD" });
    await executeKeyboardActions(actions, highlightedActions, `${key.toUpperCase()} · move ${direction.toLowerCase()}`);
  };

  const performActionInFront = async () => {
    if (!selectedAgent || !state) {
      setKeyboardStatus("Space · select an agent first");
      setError("Select an agent and wait for the environment to load.");
      return;
    }

    const deltas: Record<string, { x: number; y: number }> = {
      NORTH: { x: 0, y: -1 },
      EAST: { x: 1, y: 0 },
      SOUTH: { x: 0, y: 1 },
      WEST: { x: -1, y: 0 },
    };
    const delta = deltas[selectedAgent.orientation];
    if (!delta) {
      setError(`Unknown agent orientation: ${selectedAgent.orientation}`);
      return;
    }

    const target = { x: selectedAgent.x + delta.x, y: selectedAgent.y + delta.y, z: selectedAgent.z };
    const sameCell = (item: { x: number; y: number; z: number }) =>
      item.x === target.x && item.y === target.y && item.z === target.z;
    const casualtiesInFront = Object.values(state.casualties).filter(
      (casualty) => sameCell(casualty) && casualty.transport_status === "ON_GROUND",
    );
    const casualty = casualtiesInFront[0];
    const targetGridCell = (state.grid_cells ?? []).find(sameCell);
    const building = Object.values(state.buildings)
      .flatMap((item) => item.cells)
      .find((cell) => sameCell(cell) && !cell.collapsed);
    const fieldHospital = (state.zones ?? []).some(
      (zone) => zone.zone_type === "FIELD_HOSPITAL" && zone.cells.some(sameCell),
    );

    if (casualty) {
      setSelectedCasualtyId(casualty.id);
      if (casualty.is_covered || targetGridCell?.status === "PASSABLE") {
        await executeKeyboardActions(
          [{ action_type: "CLEAR_DEBRIS", target_coord: target }],
          ["CLEAR_DEBRIS"],
          `Space · clear debris covering ${casualty.id}`,
        );
      } else if (casualty.living_state === "DECEASED") {
        await executeKeyboardActions(
          [{ action_type: "RETRIEVE_BODY", target_casualty_id: casualty.id }],
          ["RETRIEVE_BODY"],
          `Space · retrieve ${casualty.id}`,
        );
      } else if (casualty.triage_state === "UNKNOWN") {
        await executeKeyboardActions(
          [{ action_type: "TRIAGE", target_casualty_id: casualty.id }],
          ["TRIAGE"],
          `Space · triage ${casualty.id}`,
        );
      } else {
        await executeKeyboardActions(
          [{ action_type: "LOAD_CASUALTY", target_casualty_id: casualty.id }],
          ["LOAD_CASUALTY"],
          `Space · load ${casualty.id}`,
        );
      }
      return;
    }

    if (fieldHospital && selectedAgent.payload_casualty_id) {
      await executeKeyboardActions(
        [{ action_type: "TRANSFER_CASUALTY" }],
        ["TRANSFER_CASUALTY"],
        "Space · transfer casualty to field hospital",
      );
      return;
    }

    if (building) {
      await executeKeyboardActions(
        [{ action_type: "BREACH_ENTRYWAY", target_coord: target }],
        ["BREACH_ENTRYWAY"],
        "Space · breach building entry",
      );
      return;
    }

    if (targetGridCell?.status === "PASSABLE") {
      await executeKeyboardActions(
        [{ action_type: "CLEAR_DEBRIS", target_coord: target }],
        ["CLEAR_DEBRIS"],
        "Space · clear debris",
      );
      return;
    }

    setKeyboardStatus("Space · nothing actionable directly ahead");
    setError("There is no casualty, debris, building, or field hospital directly in front of the selected agent.");
  };

  const playActionScript = async () => {
    let script: ActionScript;
    try {
      const parsed = JSON.parse(scriptJson);
      if (Array.isArray(parsed)) {
        script = { actions: parsed, delay_ms: 1000 };
      } else if (parsed && typeof parsed === "object" && Array.isArray(parsed.actions)) {
        script = parsed as ActionScript;
      } else {
        throw new Error("Enter an object with an actions array containing at least one action.");
      }
      if (!script.actions.length) {
        throw new Error("Add at least one action to the actions array.");
      }
      if (script.environment !== undefined && (typeof script.environment !== "string" || !script.environment.trim())) {
        throw new Error("environment must be a non-empty authored scenario path.");
      }
      if (script.delay_ms !== undefined && (!Number.isFinite(script.delay_ms) || script.delay_ms < 0 || script.delay_ms > 10000)) {
        throw new Error("delay_ms must be between 0 and 10000.");
      }
      for (const [index, action] of script.actions.entries()) {
        if (!action.actor_id || !action.action_type) {
          throw new Error(`Action ${index + 1} needs actor_id and action_type.`);
        }
      }
    } catch (err: any) {
      setError(`Script JSON: ${err.message ?? String(err)}`);
      return;
    }

    setIsPlayingScript(true);
    setError(null);
    try {
      if (script.environment) {
        setScriptProgress(`Loading environment · ${script.environment}`);
        const environmentResponse = await fetch(`${API_BASE}/scenario/load-from-path`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filepath: script.environment }),
        });
        if (!environmentResponse.ok) {
          const details = await environmentResponse.text();
          throw new Error(`Environment failed to load: ${details || environmentResponse.status}`);
        }
        setScenarioPath(script.environment);
        await fetchState();
      }

      const delayMs = script.delay_ms ?? 1000;
      for (const [index, action] of script.actions.entries()) {
        setScriptProgress(`${index + 1} / ${script.actions.length} · ${action.label ?? action.action_type}`);
        setSelectedAgentId(action.actor_id);
        if (action.target_casualty_id) setSelectedCasualtyId(action.target_casualty_id);

        const actionResponse = await fetch(`${API_BASE}/actions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            actions: [{
              action_id: `script_${Date.now()}_${index}`,
              actor_id: action.actor_id,
              action_type: action.action_type,
              target_casualty_id: action.target_casualty_id,
              target_coord: action.target_coord,
              start_tick: 0,
              duration: action.duration ?? 0,
            }],
          }),
        });
        if (!actionResponse.ok) {
          const details = await actionResponse.text();
          throw new Error(`Action ${index + 1} failed to queue: ${details || actionResponse.status}`);
        }

        const stepResponse = await fetch(`${API_BASE}/step`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticks: 1 }),
        });
        if (!stepResponse.ok) throw new Error(`Action ${index + 1} failed to step: ${stepResponse.status}`);
        const nextState: StateSnapshot = await stepResponse.json();
        setState(nextState);
        setEvents(nextState.events ?? []);
        const activeAgent = nextState.agents[action.actor_id];
        if (activeAgent) setZLevel(activeAgent.z);
        if (selectedZoneId && !(nextState.zones ?? []).some((zone) => zone.id === selectedZoneId)) {
          setSelectedZoneId(null);
        }
        if (delayMs > 0) await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      }
      setScriptProgress(`Complete · ${script.actions.length} actions`);
    } catch (err: any) {
      setError(`Script stopped: ${err.message ?? String(err)}`);
      await fetchState();
    } finally {
      setIsPlayingScript(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const isMovementKey = key === "w" || key === "a" || key === "s" || key === "d";
      const isActionKey = event.code === "Space";
      if ((!isMovementKey && !isActionKey) || event.repeat || isRunning || isPlayingScript || state?.ended) return;

      const target = event.target;
      if (target instanceof HTMLElement) {
        if (target.closest("input, textarea, select, [contenteditable='true']")) return;
        if (isActionKey && target.closest("button")) return;
      }

      event.preventDefault();
      if (keyboardActionInProgressRef.current) return;

      if (isActionKey) {
        void performActionInFront();
        return;
      }

      const directionByKey: Record<string, "NORTH" | "WEST" | "SOUTH" | "EAST"> = {
        w: "NORTH",
        a: "WEST",
        s: "SOUTH",
        d: "EAST",
      };
      void moveSelectedAgentInDirection(directionByKey[key], key);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  // The handler closures are refreshed whenever their state inputs change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning, isPlayingScript, selectedAgent, selectedAgentId, state]);

  useEffect(() => () => {
    if (keyboardHighlightTimerRef.current !== null) {
      window.clearTimeout(keyboardHighlightTimerRef.current);
    }
  }, []);

  useEffect(() => {
    if (!isRunning) {
      if (runIntervalRef.current !== null) {
        window.clearInterval(runIntervalRef.current);
        runIntervalRef.current = null;
      }
      return;
    }

    runIntervalRef.current = window.setInterval(() => {
      stepOneTick();
    }, 500);

    return () => {
      if (runIntervalRef.current !== null) {
        window.clearInterval(runIntervalRef.current);
        runIntervalRef.current = null;
      }
    };
  }, [isRunning]);

  // Connect to events WebSocket
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/events/stream`);

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const data: EventModel = JSON.parse(event.data);
        setEvents((prev) => {
          if (prev.some((item) =>
            item.tick === data.tick &&
            item.event_type === data.event_type &&
            item.message === data.message &&
            item.actor_id === data.actor_id
          )) {
            return prev;
          }
          return [...prev, data];
        });
      } catch (e) {
        console.error("Failed to parse event", e);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  // Start on the dev scenario so its rescue deadline is visible immediately.
  useEffect(() => {
    if (initialEnvironmentLoadRef.current) return;

    initialEnvironmentLoadRef.current = (async () => {
      let lastError = "API did not respond";
      for (let attempt = 0; attempt < 12; attempt += 1) {
        try {
          const response = await fetch(`${API_BASE}/init/dev`, {
            method: "POST",
          });
          if (!response.ok) {
            const details = await response.text();
            throw new Error(`POST /init/dev failed: ${details || response.status}`);
          }
          setScenarioPath(DEV_SCENARIO_OPTION);
          await fetchState();
          return;
        } catch (err: any) {
          lastError = err.message ?? String(err);
          if (attempt < 11) await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
      }
      setError(`Default environment failed to load: ${lastError}`);
    })();
  }, []);

  const casualties: CasualtyState[] = state
    ? Object.values(state.casualties)
    : [];
  const selectedCasualty = casualties.find((c) => c.id === selectedCasualtyId) ?? null;
  const selectedCasualtyStack = selectedCasualtyStackIds
    .map((id) => casualties.find((c) => c.id === id) ?? null)
    .filter((c): c is CasualtyState => c !== null);
  const selectedBuildingCell = state
    ? Object.values(state.buildings)
        .flatMap((b) => b.cells.map((cell) => ({ buildingId: b.id, ...cell })))
        .find((cell) => cell.z === zLevel)
    : null;
  const zones = state?.zones ?? [];
  const selectedZone = zones.find((z) => z.id === selectedZoneId) ?? null;

  return (
    <div className="App">
      <header className="App-header">
        <h1>SARSim Control Console</h1>
      </header>
      <div className="App-statusbar" role="region" aria-label="Simulation status" aria-live="polite">
        <span>Simulation: {state?.ended ? "Ended" : isRunning ? "Running" : "Paused"}</span>
        <span>WebSocket: {wsConnected ? "Connected" : "Disconnected"}</span>
      </div>
      {state?.ended && state.temporal_constraint && (
        <div className="mission-outcome-overlay">
          <div
            className={`mission-outcome ${state.success ? "mission-outcome-success" : "mission-outcome-failure"}`}
            role="alert"
            aria-live="assertive"
          >
            <span className="mission-outcome-icon" aria-hidden="true">
              {state.success ? "✓" : "✕"}
            </span>
            <span className="mission-outcome-copy">
              <strong>{state.success ? "RESCUE OBJECTIVE COMPLETE" : "RESCUE OBJECTIVE FAILED"}</strong>
              <span>
                {state.temporal_constraint.rescued_count} of {state.temporal_constraint.target_count} casualties rescued
              </span>
            </span>
          </div>
        </div>
      )}

      <div className="App-body">
        <div className="controls">
          <h2>Controls</h2>
          <button onClick={initDev}>Init Dev Scenario</button>
          <button onClick={resetScenario}>Reset Scenario</button>
          <button onClick={fetchState}>Refresh State</button>
          <button onClick={stepOneTick} disabled={state?.ended}>Step 1 Tick</button>
          <button onClick={() => setIsRunning(true)} disabled={state?.ended}>Run</button>
          <button onClick={() => setIsRunning(false)}>Pause</button>

          <details className="load-scenario-menu">
            <summary>Load Authored Scenario</summary>
            <div>
              <select
                value={scenarioPath}
                onChange={(e) => setScenarioPath(e.target.value)}
              >
                <option value={DEV_SCENARIO_OPTION}>Dev Scenario</option>
                {SCENARIO_OPTIONS.map((path) => (
                  <option key={path} value={path}>
                    {path}
                  </option>
                ))}
              </select>
              <button onClick={loadScenarioFromPath}>Load Scenario from Path</button>
              <textarea
                value={scenarioJson}
                onChange={(e) => setScenarioJson(e.target.value)}
                placeholder="Paste scenario JSON here"
                rows={5}
              />
              <button onClick={loadScenarioFromJson}>Load Scenario from JSON</button>
            </div>
          </details>
          {loading && <p>Loading...</p>}
          {state && <p>Current Tick: {state.tick}</p>}
          {error && <p className="error">Error: {error}</p>}

          <h3>Agent Selection</h3>
          <select
            value={selectedAgentId ?? ""}
            onChange={(e) => {
              setSelectedAgentId(e.target.value || null);
              e.currentTarget.blur();
            }}
          >
            <option value="">-- select agent --</option>
              {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id} ({a.agent_class})
              </option>
              ))}
          </select>

          <h3>Selected Casualty</h3>
          <p>{selectedCasualtyId ?? "None"}</p>
          {selectedCasualtyStack.length > 1 && (
            <>
              <h3>Casualties at Selected Cell</h3>
              <select
                value={selectedCasualtyId ?? ""}
                onChange={(e) => setSelectedCasualtyId(e.target.value || null)}
              >
                <option value="">-- select casualty in stack --</option>
                {selectedCasualtyStack.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} ({c.living_state}, health={c.health})
                  </option>
                ))}
              </select>
            </>
          )}

          <h3>Z-Level</h3>
          <select
            value={zLevel}
            onChange={(e) => setZLevel(Number(e.target.value))}
          >
            <option value={0}>z = 0</option>
            <option value={1}>z = 1</option>
            <option value={2}>z = 2</option>
          </select>         

          <h3>Actions</h3>
          <p className="keyboard-help">
            <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> move north, west, south, and east.
            <kbd>Space</kbd> performs the appropriate action on the tile ahead.
          </p>
          {keyboardStatus && <p className="keyboard-status" role="status">{keyboardStatus}</p>}
          <button disabled={state?.ended} data-action-type="MOVE_FORWARD" className={keyboardHighlight.includes("MOVE_FORWARD") ? "keyboard-highlight" : ""} onClick={doMoveForward}>Move Forward</button>
          <button disabled={state?.ended} data-action-type="TURN_LEFT" className={keyboardHighlight.includes("TURN_LEFT") ? "keyboard-highlight" : ""} onClick={doTurnLeft}>Turn Left</button>
          <button disabled={state?.ended} data-action-type="TURN_RIGHT" className={keyboardHighlight.includes("TURN_RIGHT") ? "keyboard-highlight" : ""} onClick={doTurnRight}>Turn Right</button>
          <button disabled={state?.ended} onClick={doAscend}>Ascend</button>
          <button disabled={state?.ended} onClick={doDescend}>Descend</button>
          <button disabled={state?.ended} data-action-type="TRIAGE" className={keyboardHighlight.includes("TRIAGE") ? "keyboard-highlight" : ""} onClick={doTriage}>Triage selected/first casualty</button>
          <button disabled={state?.ended} data-action-type="CLEAR_DEBRIS" className={keyboardHighlight.includes("CLEAR_DEBRIS") ? "keyboard-highlight" : ""} onClick={doClearDebris}>Clear Debris at Selected Casualty</button>
          <button disabled={state?.ended} data-action-type="BREACH_ENTRYWAY" className={keyboardHighlight.includes("BREACH_ENTRYWAY") ? "keyboard-highlight" : ""} onClick={doBreach}>Breach Selected Building</button>
          <button disabled={state?.ended} data-action-type="RETRIEVE_BODY" className={keyboardHighlight.includes("RETRIEVE_BODY") ? "keyboard-highlight" : ""} onClick={doRetrieveBody}>Retrieve Selected Body</button>
          <button disabled={state?.ended} data-action-type="LOAD_CASUALTY" className={keyboardHighlight.includes("LOAD_CASUALTY") ? "keyboard-highlight" : ""} onClick={doLoadCasualty}>Load Selected Casualty</button>
          <button disabled={state?.ended} onClick={doUnloadCasualty}>Unload Casualty</button>
          <button disabled={state?.ended} data-action-type="TRANSFER_CASUALTY" className={keyboardHighlight.includes("TRANSFER_CASUALTY") ? "keyboard-highlight" : ""} onClick={doTransferCasualty}>Transfer to Field Hospital</button>
          <details className="script-menu">
            <summary>Action Script</summary>
            <p>Set an authored environment and playback delay, then run actions one tick at a time.</p>
            <textarea
              aria-label="Action script JSON"
              value={scriptJson}
              onChange={(e) => setScriptJson(e.target.value)}
              rows={12}
              disabled={isPlayingScript}
            />
            <button onClick={playActionScript} disabled={isPlayingScript || isRunning || state?.ended}>
              {isPlayingScript ? "Playing Script…" : "Play Script"}
            </button>
            {scriptProgress && <p role="status">Script: {scriptProgress}</p>}
          </details>
          </div>

        <div className="panels">
          <div className="panel constraints-panel">
            <h2>Constraints</h2>
            <div className="constraints-content">
              <p><strong>Cycle:</strong> {state ? state.tick : "Waiting for scenario"}</p>
              {state?.temporal_constraint ? (
                <div className="mission-constraint" role="status">
                <p>
                  <strong>Rescue target:</strong> {state.temporal_constraint.target_count} casualties
                </p>
                <p><strong>Rescued:</strong> {state.temporal_constraint.rescued_count}</p>
                <p>
                  <strong>Deadline:</strong> {state.temporal_constraint.deadline_cycles} cycles
                  ({state.temporal_constraint.cycles_remaining} remaining)
                </p>
                </div>
              ) : (
                <p>{state ? "No temporal constraint · runs indefinitely" : "No scenario loaded"}</p>
              )}
            </div>
          </div>

          <div className="panel">
            <h2>Agents</h2>
            {agents.length === 0 && <p>No agents.</p>}
            <ul>
              {agents.map((a) => (
                <li key={a.id}>
                  <strong>{a.id}</strong> ({a.agent_class}) at ({a.x},{a.y},{a.z}){" "}
                  facing {a.orientation} | busy={a.busy_ticks_remaining} | dmg=
                  {a.damage_status ?? "none"} | payload=
                  {a.payload_casualty_id ?? "none"}
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Casualties</h2>
            {casualties.length === 0 && <p>No casualties.</p>}
            <ul>
              {casualties.map((c) => (
                <li key={c.id}>
                  <strong>{c.id}</strong> at ({c.x},{c.y},{c.z}) | health=
                  {c.health} | decay={c.decay_rate} | triage={c.triage_state} |{" "}
                  living={c.living_state} | covered=
                  {c.is_covered ? "yes" : "no"}
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Events</h2>
            {events.length === 0 && <p>No events yet.</p>}
            <ul className="events-list">
              {events.slice(-50).map((e, idx) => (
                <li key={idx}>
                  [t={e.tick}] {e.event_type}: {e.message}
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Selection Details</h2>
            {!selectedAgent && !selectedCasualty && !selectedBuildingCell && !selectedZone && selectedCasualtyStack.length === 0 && (
              <p>No selected entity details.</p>
            )}

            {selectedAgent && (
              <div>
                <h3>Agent {selectedAgent.id}</h3>
                <p>Class: {selectedAgent.agent_class}</p>
                <p>Coord: ({selectedAgent.x}, {selectedAgent.y}, {selectedAgent.z})</p>
                <p>Orientation: {selectedAgent.orientation}</p>
                <p>Busy: {selectedAgent.busy_ticks_remaining}</p>
                <p>Damage: {selectedAgent.damage_status ?? "none"}</p>
                <p>Payload: {selectedAgent.payload_casualty_id ?? "none"}</p>
              </div>
            )}

            {selectedCasualtyStack.length > 1 && (
              <div>
                <h3>Casualty Stack</h3>
                <p>{selectedCasualtyStack.length} casualties at this location.</p>
                <ul>
                  {selectedCasualtyStack.map((c) => (
                    <li key={c.id}>
                      {c.id}: {c.living_state}, health={c.health}, triage={c.triage_state}, covered={c.is_covered ? "yes" : "no"}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selectedCasualty && (
              <div>
                <h3>Casualty {selectedCasualty.id}</h3>
                <p>Coord: ({selectedCasualty.x}, {selectedCasualty.y}, {selectedCasualty.z})</p>
                <p>Health: {selectedCasualty.health}</p>
                <p>Decay: {selectedCasualty.decay_rate}</p>
                <p>Triage: {selectedCasualty.triage_state}</p>
                <p>Living: {selectedCasualty.living_state}</p>
                <p>Covered: {selectedCasualty.is_covered ? "yes" : "no"}</p>
              </div>
            )}

            {selectedBuildingCell && (
              <div>
                <h3>Building {selectedBuildingCell.buildingId}</h3>
                <p>Coord: ({selectedBuildingCell.x}, {selectedBuildingCell.y}, {selectedBuildingCell.z})</p>
                <p>Integrity: {selectedBuildingCell.integrity}</p>
                <p>Collapsed: {selectedBuildingCell.collapsed ? "yes" : "no"}</p>
              </div>
            )}

            {selectedZone && (
              <div>
                <h3>Zone {selectedZone.id}</h3>
                <p>Type: {selectedZone.zone_type}</p>
                <p>Labels: {selectedZone.labels.length > 0 ? selectedZone.labels.join(", ") : "none"}</p>
                <p>Casualties under care: {selectedZone.casualty_count_under_care}</p>
                <p>
                  Casualty IDs under care: {selectedZone.casualty_ids_under_care.length > 0
                    ? selectedZone.casualty_ids_under_care.join(", ")
                    : "none"}
                </p>
              </div>
            )}
          </div>

          <GridView
            state={state}
            size={state?.grid_size ?? 10}
            zLevel={zLevel}
            onSelectAgent={(id) => {
              setSelectedAgentId(id);
              setSelectedZoneId(null);
            }}
            onSelectCasualty={(id) => {
              setSelectedCasualtyId(id);
              setSelectedCasualtyStackIds([id]);
              setSelectedZoneId(null);
            }}
            onSelectCasualtyStack={(ids) => {
              setSelectedCasualtyStackIds(ids);
              setSelectedCasualtyId(ids[0] ?? null);
              setSelectedZoneId(null);
            }}
            onSelectZone={(id) => {
              setSelectedZoneId(id);
              setSelectedCasualtyId(null);
              setSelectedCasualtyStackIds([]);
            }}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
