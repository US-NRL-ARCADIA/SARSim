import * as THREE from "/ui/vendor/three.module.js";

const viewers = new WeakMap();
const layerHeight = 1.45;
const casualtyStackHeight = 0.23;

export function renderThreeScene(host, source, options = {}) {
  let viewer = viewers.get(host);
  if (!viewer) {
    viewer = new SceneViewer(host);
    viewers.set(host, viewer);
  }
  viewer.update(normalizeScene(source, options), options);
}

export function disposeThreeScene(host) {
  const viewer = viewers.get(host);
  if (viewer) viewer.dispose();
  viewers.delete(host);
}

class SceneViewer {
  constructor(host) {
    this.host = host;
    this.azimuth = Math.PI * 0.72;
    this.elevation = Math.PI * 0.24;
    this.radius = 15;
    this.target = new THREE.Vector3();
    this.pointer = null;
    this.dragged = false;
    this.onSelect = null;
    this.host.innerHTML = `<div class="three-shell">
      <div class="three-toolbar">
        <span><b>3D scene</b><small data-three-summary>Waiting for scenario…</small></span>
        <button data-three-view="iso">Isometric</button>
        <button data-three-view="top">Top</button>
        <button data-three-view="fit">Fit scene</button>
      </div>
      <div class="three-stage" data-three-stage>
        <div class="three-help">Drag to orbit · Shift/right-drag to pan · Scroll to zoom · Click an entity to select</div>
        <div class="three-legend"><span><i class="three-swatch wall"></i>Wall</span><span><i class="three-swatch debris"></i>Debris</span><span><i class="three-swatch smoke"></i>Smoke</span><span><i class="three-swatch building"></i>Building</span><span><i class="three-swatch casualty"></i>Casualty</span><span><i class="three-swatch agent"></i>Agent</span></div>
      </div>
    </div>`;
    this.stage = host.querySelector("[data-three-stage]");
    this.summary = host.querySelector("[data-three-summary]");
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xe9eef4);
    this.scene.fog = new THREE.Fog(0xe9eef4, 24, 55);
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.05, 120);
    this.renderer = this.createRenderer();
    this.world = new THREE.Group();
    this.scene.add(this.world);
    this.scene.add(new THREE.HemisphereLight(0xf7fbff, 0x6c7b68, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 2.7);
    sun.position.set(8, 14, 9);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -14;
    sun.shadow.camera.right = 14;
    sun.shadow.camera.top = 14;
    sun.shadow.camera.bottom = -14;
    this.scene.add(sun);
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.bindControls();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.stage);
    this.resize();
  }

  createRenderer() {
    try {
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
      renderer.domElement.tabIndex = 0;
      renderer.domElement.setAttribute("aria-label", "Interactive three-dimensional SARSim scene");
      this.stage.prepend(renderer.domElement);
      return renderer;
    } catch (error) {
      this.stage.insertAdjacentHTML("afterbegin", `<div class="three-error">3D rendering is unavailable: ${escapeHtml(error.message || error)}</div>`);
      return null;
    }
  }

  bindControls() {
    this.host.addEventListener("click", event => {
      const button = event.target.closest("[data-three-view]");
      if (!button) return;
      const view = button.dataset.threeView;
      if (view === "top") {
        this.azimuth = -Math.PI / 2;
        this.elevation = Math.PI / 2 - 0.025;
      } else if (view === "iso") {
        this.azimuth = Math.PI * 0.72;
        this.elevation = Math.PI * 0.24;
      } else {
        this.fitCamera();
      }
      this.render();
    });
    if (!this.renderer) return;
    const canvas = this.renderer.domElement;
    canvas.addEventListener("contextmenu", event => event.preventDefault());
    canvas.addEventListener("pointerdown", event => {
      canvas.setPointerCapture(event.pointerId);
      this.pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, button: event.button, shift: event.shiftKey };
      this.dragged = false;
    });
    canvas.addEventListener("pointermove", event => {
      if (!this.pointer || event.pointerId !== this.pointer.id) return;
      const dx = event.clientX - this.pointer.x;
      const dy = event.clientY - this.pointer.y;
      if (Math.abs(dx) + Math.abs(dy) > 2) this.dragged = true;
      if (this.pointer.shift || this.pointer.button === 2) this.pan(dx, dy);
      else {
        this.azimuth -= dx * 0.009;
        this.elevation = THREE.MathUtils.clamp(this.elevation + dy * 0.007, 0.08, Math.PI / 2 - 0.02);
      }
      this.pointer.x = event.clientX;
      this.pointer.y = event.clientY;
      this.render();
    });
    canvas.addEventListener("pointerup", event => {
      if (this.pointer && !this.dragged) this.pick(event);
      this.pointer = null;
    });
    canvas.addEventListener("pointercancel", () => { this.pointer = null; });
    canvas.addEventListener("wheel", event => {
      event.preventDefault();
      this.radius = THREE.MathUtils.clamp(this.radius * Math.exp(event.deltaY * 0.001), 3, 70);
      this.render();
    }, { passive: false });
  }

  update(data, options) {
    this.onSelect = options.onSelect || null;
    this.clearWorld();
    if (!data) {
      this.summary.textContent = "Waiting for scenario…";
      this.render();
      return;
    }
    this.data = data;
    const extent = `${data.size}:${data.levels}`;
    const refit = extent !== this.extent;
    this.extent = extent;
    this.summary.textContent = `${data.size}×${data.size}×${data.levels} · ${data.agents.length} agents · ${data.casualties.length} casualties · ${sensorLabel(data.sensorRegime || "FULL")}`;
    this.buildGround(data);
    this.buildVisibilityFootprint(data);
    this.buildZones(data);
    this.buildCells(data);
    this.buildBuildings(data);
    this.buildCasualties(data);
    this.buildAgents(data);
    if (refit) this.fitCamera();
    this.render();
  }

  buildGround(data) {
    const half = data.size / 2;
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(data.size, data.size),
      new THREE.MeshStandardMaterial({ color: 0xf7f9fb, roughness: 0.96, metalness: 0 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.035;
    floor.receiveShadow = true;
    this.world.add(floor);
    for (let level = 0; level < data.levels; level += 1) {
      const grid = new THREE.GridHelper(data.size, data.size, level === 0 ? 0x8293a5 : 0xb3bec9, 0xcbd5df);
      grid.position.set(0, level * layerHeight + 0.005, 0);
      grid.material.transparent = true;
      grid.material.opacity = level === 0 ? 0.58 : 0.16;
      this.world.add(grid);
    }
    const border = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(data.size, Math.max(0.03, (data.levels - 1) * layerHeight), data.size)),
      new THREE.LineBasicMaterial({ color: 0x91a0ae, transparent: true, opacity: 0.18 }),
    );
    border.position.y = (data.levels - 1) * layerHeight / 2;
    this.world.add(border);
    this.target.set(0, Math.max(0.3, (data.levels - 1) * layerHeight * 0.28), 0);
    this.radius = Math.max(this.radius, data.size * 1.28);
    this.half = half;
  }

  buildVisibilityFootprint(data) {
    if (!data.visibleCells?.length) return;
    for (const coord of data.visibleCells) {
      const tile = new THREE.Mesh(
        new THREE.BoxGeometry(0.94, 0.025, 0.94),
        new THREE.MeshStandardMaterial({ color: 0x72a9d3, transparent: true, opacity: 0.38, roughness: 0.85, depthWrite: false }),
      );
      tile.position.copy(this.position(coord, 0.018));
      this.world.add(tile);
    }
  }

  buildZones(data) {
    for (const zone of data.zones) {
      const hospital = zone.zone_type === "FIELD_HOSPITAL";
      for (const coord of zone.cells || []) {
        const mesh = new THREE.Mesh(
          new THREE.BoxGeometry(0.92, 0.035, 0.92),
          new THREE.MeshStandardMaterial({ color: hospital ? 0x5e9b77 : 0x5c8db8, transparent: true, opacity: 0.68, roughness: 0.8 }),
        );
        mesh.position.copy(this.position(coord, 0.025));
        mesh.userData.sarsim = { kind: "zone", id: zone.id, coord };
        this.world.add(mesh);
      }
    }
  }

  buildCells(data) {
    const buildingCells = new Set(data.buildings.flatMap(building => (building.cells || []).map(cell => coordinateKey(coordinate(cell)))));
    for (const cell of data.cells) {
      const coord = coordinate(cell);
      if (cell.status === "IMPASSABLE" && !buildingCells.has(coordinateKey(coord))) {
        const wall = this.box(0x9ba7b3, [0.88, 0.82, 0.88], coord, 0.41);
        wall.material.roughness = 0.9;
        wall.userData.sarsim = { kind: "cell", coord };
      } else if (cell.status === "PASSABLE") {
        const group = new THREE.Group();
        group.position.copy(this.position(coord, 0.08));
        for (let i = 0; i < 4; i += 1) {
          const chunk = new THREE.Mesh(
            new THREE.BoxGeometry(0.31, 0.14 + i * 0.018, 0.24),
            new THREE.MeshStandardMaterial({ color: i % 2 ? 0xb68a55 : 0x9c7952, roughness: 1 }),
          );
          chunk.position.set((i % 2 - 0.5) * 0.34, i * 0.035, (Math.floor(i / 2) - 0.5) * 0.3);
          chunk.rotation.y = i * 0.58;
          chunk.castShadow = true;
          group.add(chunk);
        }
        group.userData.sarsim = { kind: "cell", coord };
        this.world.add(group);
      }
      if ((cell.smoke_density || 0) > 0) this.addSmoke(coord, cell.smoke_density);
    }
  }

  buildBuildings(data) {
    for (const building of data.buildings) {
      for (const cell of building.cells || []) {
        const coord = coordinate(cell);
        const height = cell.collapsed ? 0.24 : layerHeight * 0.96;
        const mesh = this.box(cell.collapsed ? 0x927965 : 0x8175a7, [0.78, height, 0.78], coord, height / 2);
        mesh.material.roughness = 0.82;
        mesh.userData.sarsim = { kind: "building", id: building.id, coord };
        const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color: 0x51486f, transparent: true, opacity: 0.5 }));
        mesh.add(edges);
      }
    }
  }

  buildCasualties(data) {
    const stackLevels = hospitalCasualtyStackLevels(data);
    for (const casualty of data.casualties) {
      if (casualty.transport_status === "LOADED") continue;
      const coord = coordinate(casualty);
      const group = new THREE.Group();
      const color = casualty.living_state === "DECEASED" ? 0xa94f59 : casualty.triage_state !== "UNKNOWN" ? 0x4f8a6a : 0xc47847;
      const body = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.13, 0.2), new THREE.MeshStandardMaterial({ color, roughness: 0.72 }));
      body.castShadow = true;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.115, 16, 10), new THREE.MeshStandardMaterial({ color: 0xd5a17d, roughness: 0.8 }));
      head.position.x = 0.34;
      head.castShadow = true;
      group.add(body, head);
      const hospitalStackLevel = stackLevels.get(casualty.id) || 0;
      group.position.copy(this.position(coord, 0.13 + hospitalStackLevel * casualtyStackHeight));
      group.userData.sarsim = { kind: "casualty", id: casualty.id, coord };
      this.world.add(group);
      if (casualty.is_covered) {
        const cover = this.box(0xa98356, [0.62, 0.1, 0.42], coord, 0.23);
        cover.material.transparent = true;
        cover.material.opacity = 0.78;
      }
    }
  }

  buildAgents(data) {
    for (const agent of data.agents) {
      const coord = coordinate(agent);
      const group = agent.agent_class === "UAV" ? this.uav(agent) : this.ugv(agent);
      group.position.copy(this.position(coord, agent.agent_class === "UAV" ? 0.42 : 0.2));
      group.rotation.y = { NORTH: 0, EAST: -Math.PI / 2, SOUTH: Math.PI, WEST: Math.PI / 2 }[agent.orientation] || 0;
      group.userData.sarsim = { kind: "agent", id: agent.id, coord };
      this.world.add(group);
    }
  }

  ugv(agent) {
    const group = new THREE.Group();
    const blue = new THREE.MeshStandardMaterial({ color: 0x3f79a8, roughness: 0.58, metalness: 0.12 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x293846, roughness: 0.9 });
    const chassis = new THREE.Mesh(new THREE.BoxGeometry(0.58, 0.22, 0.72), blue);
    const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.2, 0.34), blue);
    cabin.position.set(0, 0.2, 0.08);
    chassis.castShadow = cabin.castShadow = true;
    group.add(chassis, cabin);
    for (const x of [-0.34, 0.34]) for (const z of [-0.23, 0.23]) {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.1, 14), dark);
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, -0.08, z);
      group.add(wheel);
    }
    group.add(this.headingArrow());
    if (agent.payload_casualty_id) {
      const payload = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.11, 0.38), new THREE.MeshStandardMaterial({ color: 0xc47847 }));
      payload.position.y = 0.34;
      group.add(payload);
    }
    return group;
  }

  uav() {
    const group = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({ color: 0x7365a0, roughness: 0.45, metalness: 0.18 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x354052, roughness: 0.72 });
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.22, 18, 12), material);
    body.scale.y = 0.55;
    body.castShadow = true;
    group.add(body);
    for (const rotation of [Math.PI / 4, -Math.PI / 4]) {
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.055, 0.055), material);
      arm.rotation.y = rotation;
      group.add(arm);
    }
    for (const x of [-0.29, 0.29]) for (const z of [-0.29, 0.29]) {
      const rotor = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.022, 8, 20), dark);
      rotor.rotation.x = Math.PI / 2;
      rotor.position.set(x, 0.04, z);
      group.add(rotor);
    }
    group.add(this.headingArrow());
    return group;
  }

  headingArrow() {
    const arrow = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.28, 12), new THREE.MeshStandardMaterial({ color: 0xf4c468, roughness: 0.55 }));
    arrow.rotation.x = -Math.PI / 2;
    arrow.position.set(0, 0.34, -0.43);
    return arrow;
  }

  addSmoke(coord, density) {
    const group = new THREE.Group();
    group.position.copy(this.position(coord, 0.42));
    for (let i = 0; i < 4; i += 1) {
      const puff = new THREE.Mesh(
        new THREE.SphereGeometry(0.24 + i * 0.035, 14, 10),
        new THREE.MeshStandardMaterial({ color: 0x72808d, transparent: true, opacity: 0.12 + density * 0.12, roughness: 1, depthWrite: false }),
      );
      puff.position.set((i % 2 - 0.5) * 0.25, i * 0.15, (Math.floor(i / 2) - 0.5) * 0.2);
      group.add(puff);
    }
    group.userData.sarsim = { kind: "smoke", coord };
    this.world.add(group);
  }

  box(color, dimensions, coord, lift) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...dimensions), new THREE.MeshStandardMaterial({ color }));
    mesh.position.copy(this.position(coord, lift));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    this.world.add(mesh);
    return mesh;
  }

  position(value, lift = 0) {
    const coord = coordinate(value);
    return new THREE.Vector3(coord.x - this.half + 0.5, coord.z * layerHeight + lift, coord.y - this.half + 0.5);
  }

  pan(dx, dy) {
    const scale = this.radius * 0.0018;
    const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrix, 0);
    const forward = new THREE.Vector3(this.camera.position.x - this.target.x, 0, this.camera.position.z - this.target.z).normalize();
    this.target.addScaledVector(right, -dx * scale).addScaledVector(forward, -dy * scale);
  }

  pick(event) {
    if (!this.onSelect || !this.renderer) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const hits = this.raycaster.intersectObjects(this.world.children, true);
    for (const hit of hits) {
      let object = hit.object;
      while (object && !object.userData.sarsim) object = object.parent;
      if (object?.userData.sarsim) {
        this.onSelect(object.userData.sarsim);
        return;
      }
    }
  }

  fitCamera() {
    if (!this.data) return;
    this.target.set(0, Math.max(0.35, (this.data.levels - 1) * layerHeight * 0.3), 0);
    this.radius = Math.max(7, this.data.size * 1.28 + this.data.levels * 0.6);
  }

  resize() {
    if (!this.renderer) return;
    const width = Math.max(1, this.stage.clientWidth);
    const height = Math.max(1, this.stage.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    this.render();
  }

  render() {
    if (!this.renderer) return;
    const horizontal = Math.cos(this.elevation) * this.radius;
    this.camera.position.set(
      this.target.x + Math.cos(this.azimuth) * horizontal,
      this.target.y + Math.sin(this.elevation) * this.radius,
      this.target.z + Math.sin(this.azimuth) * horizontal,
    );
    this.camera.lookAt(this.target);
    this.renderer.render(this.scene, this.camera);
  }

  clearWorld() {
    for (const child of [...this.world.children]) {
      child.traverse(object => {
        object.geometry?.dispose();
        if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
        else object.material?.dispose();
      });
      this.world.remove(child);
    }
  }

  dispose() {
    this.resizeObserver.disconnect();
    this.clearWorld();
    this.renderer?.dispose();
    this.renderer?.forceContextLoss();
  }
}

function normalizeScene(source, options = {}) {
  if (!source) return null;
  if (source.grid) {
    const cells = source.grid.cells.map(cell => ({ ...cell, ...cell.coord, smoke_density: 0 }));
    for (const smoke of source.grid.smoke || []) {
      let cell = cells.find(candidate => sameCoord(candidate, smoke.coord));
      if (!cell) {
        cell = { ...smoke.coord, status: "UNOCCUPIED", smoke_density: 0 };
        cells.push(cell);
      }
      cell.smoke_density = smoke.density;
    }
    return {
      size: source.grid.N,
      levels: source.grid.Z,
      cells,
      agents: (source.agents || []).map(item => ({ ...item, ...item.coord })),
      casualties: (source.casualties || []).map(item => ({ ...item, ...item.coord })),
      buildings: (source.buildings || []).map(building => ({ ...building, cells: (building.cells || []).map(cell => ({ ...cell, ...cell.coord })) })),
      zones: source.zones || [],
    };
  }
  const visible = options.visibleCells || null;
  const canSee = value => !visible || visible.has(coordinateKey(coordinate(value)));
  return {
    size: source.grid_size,
    levels: source.z_levels,
    cells: (source.grid_cells || []).filter(canSee),
    agents: Object.values(source.agents || {}).filter(canSee),
    casualties: Object.values(source.casualties || {}).filter(canSee),
    buildings: Object.values(source.buildings || {}).map(building => ({ ...building, cells: (building.cells || []).filter(canSee) })).filter(building => building.cells.length),
    zones: (source.zones || []).map(zone => ({ ...zone, cells: (zone.cells || []).filter(canSee) })).filter(zone => zone.cells.length),
    visibleCells: visible ? [...visible].map(parseCoordinateKey) : [],
    sensorRegime: options.sensorRegime || "FULL",
  };
}

function hospitalCasualtyStackLevels(data) {
  const admittedIds = new Set(
    data.zones
      .filter(zone => zone.zone_type === "FIELD_HOSPITAL")
      .flatMap(zone => zone.casualty_ids_under_care || []),
  );
  const countsByCoordinate = new Map();
  const levelsByCasualtyId = new Map();
  for (const casualty of data.casualties) {
    if (!admittedIds.has(casualty.id) || casualty.transport_status === "LOADED") continue;
    const key = coordinateKey(coordinate(casualty));
    const level = countsByCoordinate.get(key) || 0;
    levelsByCasualtyId.set(casualty.id, level);
    countsByCoordinate.set(key, level + 1);
  }
  return levelsByCasualtyId;
}

function coordinate(value) {
  return value?.coord || value || { x: 0, y: 0, z: 0 };
}

function sameCoord(a, b) {
  const left = coordinate(a);
  const right = coordinate(b);
  return left.x === right.x && left.y === right.y && left.z === right.z;
}

function coordinateKey(coord) {
  return `${coord.x},${coord.y},${coord.z}`;
}

function parseCoordinateKey(key) {
  const [x, y, z] = key.split(",").map(Number);
  return { x, y, z };
}

function sensorLabel(regime) {
  return ({ FULL: "full view", FOV_CONE: "FOV cone", MINIGRID_3: "MiniGrid 3-wide" })[regime] || regime;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}
