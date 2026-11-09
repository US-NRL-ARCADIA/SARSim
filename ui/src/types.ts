export interface AgentState {
  id: string;
  x: number;
  y: number;
  z: number;
  orientation: string;
  agent_class: string;
  busy_ticks_remaining: number;
  damage_status: string | null;
  payload_casualty_id: string | null;
}

export interface CasualtyState {
  id: string;
  x: number;
  y: number;
  z: number;
  health: number;
  decay_rate: number;
  is_covered: boolean;
  triage_state: string;
  living_state: string;
  transport_status: string;
}

export interface BuildingCellState {
  x: number;
  y: number;
  z: number;
  integrity: number;
  collapsed: boolean;
}

export interface BuildingState {
  id: string;
  cells: BuildingCellState[];
}

export interface GridCellState {
  x: number;
  y: number;
  z: number;
  status: string;
  smoke_density: number;
}

export interface ZoneCellState {
  x: number;
  y: number;
  z: number;
}

export interface ZoneState {
  id: string;
  zone_type: string;
  cells: ZoneCellState[];
  labels: string[];
  casualty_count_under_care: number;
  casualty_ids_under_care: string[];
}

export interface StateSnapshot {
  tick: number;
  temporal_constraint: TemporalConstraintState | null;
  ended: boolean;
  success: boolean | null;
  grid_size?: number;
  z_levels?: number;
  agents: Record<string, AgentState>;
  casualties: Record<string, CasualtyState>;
  buildings: Record<string, BuildingState>;
  zones?: ZoneState[];
  grid_cells?: GridCellState[];
  events?: EventModel[];
}

export interface TemporalConstraintState {
  type: string;
  target_count: number;
  deadline_cycles: number;
  rescued_count: number;
  cycles_remaining: number;
}

export interface EventModel {
  tick: number;
  event_type: string;
  message: string;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
}
