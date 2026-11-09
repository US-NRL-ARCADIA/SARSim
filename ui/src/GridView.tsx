import React from "react";
import { StateSnapshot, AgentState, CasualtyState, BuildingCellState } from "./types";

interface GridViewProps {
  state: StateSnapshot | null;
  size?: number; // grid size (N)
  zLevel?: number; // which z to show
  onSelectAgent?: (agentId: string) => void;
  onSelectCasualty?: (casualtyId: string) => void;
  onSelectCasualtyStack?: (casualtyIds: string[]) => void;
  onSelectZone?: (zoneId: string) => void;
}

const GridView: React.FC<GridViewProps> = ({
  state,
  size = 10,
  zLevel = 0,
  onSelectAgent,
  onSelectCasualty,
  onSelectCasualtyStack,
  onSelectZone,
}) => {
  if (!state) {
    return <div>No state loaded.</div>;
  }

  // Filter agents and casualties by z-level
  const agents: AgentState[] = Object.values(state.agents).filter(
    (a) => a.z === zLevel
  );
  const casualties: CasualtyState[] = Object.values(state.casualties).filter(
    (c) => c.z === zLevel && c.transport_status !== "LOADED"
  );

  const buildingCells: BuildingCellState[] = Object.values(state.buildings)
    .flatMap((b) => b.cells)
    .filter((cell) => cell.z === zLevel);

  const gridCells = (state.grid_cells ?? []).filter((cell) => cell.z === zLevel);
  const zones = (state.zones ?? []).filter((zone) =>
    zone.cells.some((cell) => cell.z === zLevel)
  );

  const groundBuildingCells: BuildingCellState[] = Object.values(state.buildings)
    .flatMap((b) => b.cells)
    .filter((cell) => cell.z === 0);

  // Build lookups by (x,y)
  const agentByCoord = new Map<string, AgentState[]>();
  const casualtyByCoord = new Map<string, CasualtyState[]>();
  const buildingByCoord = new Map<string, BuildingCellState[]>();
  const groundBuildingByCoord = new Map<string, BuildingCellState[]>();
  const gridCellByCoord = new Map<string, { status: string; smoke_density: number }>();
  const zoneByCoord = new Map<string, { zoneIds: string[]; zoneTypes: string[]; hospitalCount: number; hospitalCasualtyIds: string[] }>();

  for (const a of agents) {
    const key = `${a.x},${a.y}`;
    const existing = agentByCoord.get(key) ?? [];
    existing.push(a);
    agentByCoord.set(key, existing);
  }

  for (const c of casualties) {
    const key = `${c.x},${c.y}`;
    const existing = casualtyByCoord.get(key) ?? [];
    existing.push(c);
    casualtyByCoord.set(key, existing);
  }

  for (const cell of buildingCells) {
    const key = `${cell.x},${cell.y}`;
    const existing = buildingByCoord.get(key) ?? [];
    existing.push(cell);
    buildingByCoord.set(key, existing);
  }

  for (const cell of groundBuildingCells) {
    const key = `${cell.x},${cell.y}`;
    const existing = groundBuildingByCoord.get(key) ?? [];
    existing.push(cell);
    groundBuildingByCoord.set(key, existing);
  }

  for (const cell of gridCells) {
    const key = `${cell.x},${cell.y}`;
    gridCellByCoord.set(key, {
      status: cell.status,
      smoke_density: cell.smoke_density,
    });
  }

  for (const zone of zones) {
    for (const cell of zone.cells) {
      if (cell.z !== zLevel) {
        continue;
      }
      const key = `${cell.x},${cell.y}`;
      const existing = zoneByCoord.get(key) ?? {
        zoneIds: [],
        zoneTypes: [],
        hospitalCount: 0,
        hospitalCasualtyIds: [],
      };
      existing.zoneIds.push(zone.id);
      existing.zoneTypes.push(zone.zone_type);
      if (zone.zone_type === "FIELD_HOSPITAL") {
        existing.hospitalCount = Math.max(
          existing.hospitalCount,
          zone.casualty_count_under_care ?? 0
        );
        existing.hospitalCasualtyIds = zone.casualty_ids_under_care ?? [];
      }
      zoneByCoord.set(key, existing);
    }
  }

  const rows = [];
  // Lower y values render at the top so north (y - 1) points upward.
  for (let y = 0; y < size; y++) {
    const cells = [];
    for (let x = 0; x < size; x++) {
      const key = `${x},${y}`;
      const cellAgents = agentByCoord.get(key) ?? [];
      const cellCasualties = casualtyByCoord.get(key) ?? [];
      const cellBuildings = buildingByCoord.get(key) ?? [];
      const groundBuildings = groundBuildingByCoord.get(key) ?? [];
      const gridCell = gridCellByCoord.get(key);
      const zoneInfo = zoneByCoord.get(key) ?? { zoneIds: [], zoneTypes: [], hospitalCount: 0, hospitalCasualtyIds: [] };
      const zoneTypes = zoneInfo.zoneTypes;

      let content = "";
      let className = "grid-cell";
      let agentOrientation: string | null = null;
      const badges: string[] = [];

      if (zoneTypes.includes("FIELD_HOSPITAL")) {
        className += " grid-cell-field-hospital";
        badges.push("HOSP");
        badges.push(`CARE:${zoneInfo.hospitalCount}`);
        if (zoneInfo.hospitalCasualtyIds.length > 0) {
          badges.push(`IDS:${zoneInfo.hospitalCasualtyIds.join(",")}`);
        }
      }

      if (gridCell?.status === "PASSABLE") {
        className += " grid-cell-debris";
        badges.push("DEB");
      } else if (gridCell?.status === "IMPASSABLE") {
        className += " grid-cell-wall";
        badges.push("WALL");
      }

      if ((gridCell?.smoke_density ?? 0) > 0) {
        className += " grid-cell-smoke";
        badges.push(`SMK:${(gridCell?.smoke_density ?? 0).toFixed(1)}`);
      }

      if (cellBuildings.length > 0) {
        className += cellBuildings.some((b) => b.collapsed)
          ? " grid-cell-building-collapsed"
          : " grid-cell-building";
        const integrity = cellBuildings[0].integrity;
        badges.push(`B:${integrity.toFixed(1)}`);
      } else if (groundBuildings.length > 0 && zLevel !== 0) {
        className += groundBuildings.some((b) => b.collapsed)
          ? " grid-cell-building-footprint-collapsed"
          : " grid-cell-building-footprint";
        badges.push("B↓");
      }

      const casualtyCovered = cellCasualties.some((c) => c.is_covered);
      if (casualtyCovered) {
        className += " grid-cell-covered";
        badges.push("CVR");
      }

      if (cellAgents.length > 0) {
        const a = cellAgents[0];
        agentOrientation = a.orientation.toLowerCase();
        const altitudeBadge = a.agent_class === "UAV" ? `UAV:z${a.z}` : a.agent_class;
        badges.push(altitudeBadge);
        if (a.payload_casualty_id) {
          badges.push(`PAY:${a.payload_casualty_id}`);
          className += " grid-cell-agent-payload";
        }
        content = `A:${a.id}`;
        className += a.agent_class === "UAV" ? " grid-cell-agent-uav" : " grid-cell-agent";
      } else if (cellCasualties.length > 0) {
        const c = cellCasualties[0];
        if (cellCasualties.length > 1) {
          badges.push(`C×${cellCasualties.length}`);
        }
        if (c.living_state === "DECEASED") {
          className += " grid-cell-casualty-deceased";
          content = cellCasualties.length > 1 ? `C:${c.id} +${cellCasualties.length - 1}` : `C:${c.id} (X)`;
        } else if (c.triage_state !== "UNKNOWN") {
          className += " grid-cell-casualty-triaged";
          content = cellCasualties.length > 1 ? `C:${c.id} +${cellCasualties.length - 1}` : `C:${c.id} (T)`;
        } else {
          className += " grid-cell-casualty";
          content = cellCasualties.length > 1 ? `C:${c.id} +${cellCasualties.length - 1}` : `C:${c.id}`;
        }
      } else if (gridCell?.status === "UNOCCUPIED") {
        className += " grid-cell-empty";
      }

      const handleClick = () => {
        if (cellAgents.length > 0 && onSelectAgent) {
          onSelectAgent(cellAgents[0].id);
        } else if (cellCasualties.length > 0) {
          if (cellCasualties.length === 1 && onSelectCasualty) {
            onSelectCasualty(cellCasualties[0].id);
          } else if (cellCasualties.length > 1 && onSelectCasualtyStack) {
            onSelectCasualtyStack(cellCasualties.map((c) => c.id));
          } else if (onSelectCasualty) {
            onSelectCasualty(cellCasualties[0].id);
          }
        } else if (zoneInfo.zoneIds.length > 0 && onSelectZone) {
          onSelectZone(zoneInfo.zoneIds[0]);
        }
      };

      cells.push(
        <div key={key} className={className} onClick={handleClick}>
          <span className="grid-cell-coord">
            {x},{y}
          </span>
          <span className="grid-cell-badges">{badges.join(" ")}</span>
          {cellAgents.length > 0 && agentOrientation ? (
            <span className="grid-cell-content agent-cell-content" aria-label={`Agent facing ${agentOrientation}`}>
              <span className={`agent-direction agent-direction-${agentOrientation}`} aria-hidden="true" />
              {content}
            </span>
          ) : (
            <span className="grid-cell-content">{content}</span>
          )}
        </div>
      );
    }
    rows.push(
      <div key={`row-${y}`} className="grid-row">
        {cells}
      </div>
    );
  }

  return (
    <div className="grid-view">
      <h2>Grid View (z={zLevel})</h2>
      <div className="grid-legend">
        <span className="legend-item legend-agent">UGV</span>
        <span className="legend-item legend-agent-uav">UAV</span>
        <span className="legend-item legend-casualty">Casualty</span>
        <span className="legend-item legend-casualty">Casualty stack (C×N)</span>
        <span className="legend-item legend-casualty-triaged">Triaged</span>
        <span className="legend-item legend-building">Building</span>
        <span className="legend-item legend-building-collapsed">Collapsed</span>
        <span className="legend-item legend-building-footprint">Building below</span>
        <span className="legend-item legend-debris">Debris</span>
        <span className="legend-item legend-wall">Wall</span>
        <span className="legend-item legend-smoke">Smoke</span>
        <span className="legend-item legend-covered">Covered casualty</span>
        <span className="legend-item legend-agent-payload">Agent carrying casualty</span>
        <span className="legend-item legend-field-hospital">Field hospital</span>
      </div>
      <div className="grid">{rows}</div>
    </div>
  );
};

export default GridView;
